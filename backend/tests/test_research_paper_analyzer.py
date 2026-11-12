import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.handwritten_page import HandwrittenPage
from app.models.research_paper_analysis import ResearchPaperAnalysis
from app.models.user import User
from app.schemas.research_paper import MISSING_FIELD_TEXT
from app.services.embedding_services import generate_embedding
from app.services.handwriting.ollama_client import OllamaError


SAMPLE_PAPER_PAGES = [
    (
        1,
        "Neural Graph Intrusion Detection for Encrypted Network Flows\n"
        "Authors: Priya Nair, Arvind Menon\n"
        "Department of Computer Science, Indian Institute of Technology Madras\n"
        "priya@iitm.ac.in\n"
        "Proceedings of IEEE Security Symposium (2025) | DOI: 10.1109/SEC.2025.00412\n"
        "Abstract\n"
        "Encrypted traffic hides payload signatures from traditional firewall inspection [1]. "
        "The critical problem is detecting malicious flows without decrypting user sessions [2]. "
        "We propose FlowGNN, a lightweight graph-based deep learning framework that models flow metadata graphs.\n"
        "Keywords: Encrypted Traffic, Graph Neural Networks, Intrusion Detection",
    ),
    (
        2,
        "1. Introduction\n"
        "Motivation stems from the rapid growth of TLS 1.3 adoption across enterprise networks [3]. "
        "Our research objective is to classify benign and malicious flows under strict latency budgets. "
        "Research Question: Can temporal flow graphs achieve high recall without payload inspection?\n"
        "2. Methodology\n"
        "Our methodology type is an empirical quantitative study combining graph construction with message passing. "
        "The architecture uses a 3-layer GraphSAGE encoder implemented in PyTorch Geometric.\n"
        "2.1 Dataset and Preprocessing\n"
        "We evaluate on the CICIDS-2017 benchmark dataset containing 120,000 flow samples with an 80/20 train-test split. "
        "Preprocessing applies min-max normalization and session windowing over packet inter-arrival timings.",
    ),
    (
        3,
        "3. Experiments and Results\n"
        "Experimental setup runs on an Intel Xeon CPU testbed with 32 GB RAM. "
        "Evaluation metrics include Accuracy, Precision, Recall, F1-Score, and inference latency. "
        "Compared against Random Forest and CNN baseline methods [4], FlowGNN outperforms baselines as summarized in Table 1 and Figure 2.\n"
        "Table 1 reports FlowGNN Accuracy = 96.4% compared to the CNN baseline accuracy of 92.2% and F1-score = 95.8%, "
        "with inference latency = 4.5 ms.\n"
        "Equation 1 defines the edge aggregation weight, and Algorithm 1 outlines flow batching.",
    ),
    (
        4,
        "4. Conclusion\n"
        "In conclusion, FlowGNN demonstrates reliable encrypted flow classification without payload decryption.\n"
        "Limitations: A key limitation is sensitivity to extreme packet reordering under multipath routing.\n"
        "Future Work: In future work, we will extend FlowGNN to federated multi-campus deployment.\n"
        "References\n"
        "[1] Anderson B., McGrew D., TLS Traffic Classification, IEEE S&P, 2020.\n"
        "[2] Chen L. et al., Encrypted Flow Graphs, ACM CCS, 2022.",
    ),
]


class TestResearchPaperAnalyzer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=cls.engine
        )

        def override_get_db():
            db = cls.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        cls.prev_override = app.dependency_overrides.get(get_db)
        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        if cls.prev_override is not None:
            app.dependency_overrides[get_db] = cls.prev_override
        else:
            app.dependency_overrides.pop(get_db, None)

    def setUp(self):
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.TestingSessionLocal()
        self.user = User(
            id=1,
            email="research_owner@example.com",
            full_name="Research Owner",
            password_hash=hash_password("Pass123!"),
            is_verified=True,
        )
        self.other_user = User(
            id=2,
            email="other_tenant@example.com",
            full_name="Other Tenant",
            password_hash=hash_password("Pass123!"),
            is_verified=True,
        )
        self.db.add_all([self.user, self.other_user])
        self.db.commit()
        self.headers = {
            "Authorization": f"Bearer {create_access_token({'sub': str(self.user.id)})}"
        }
        self.other_headers = {
            "Authorization": f"Bearer {create_access_token({'sub': str(self.other_user.id)})}"
        }

    def tearDown(self):
        self.db.close()

    def _seed_doc(self, user_id: int, filename: str, pages: list[tuple[int, str]], doc_type: str = "PDF", is_hw: bool = False) -> Document:
        full_text = "\n\n".join(txt for _, txt in pages)
        doc = Document(
            user_id=user_id,
            filename=filename,
            document_type=doc_type,
            file_path=f"uploads/{filename}",
            extracted_text=full_text,
            text_length=len(full_text),
            is_handwritten=is_hw,
            processing_status="completed",
            processing_progress=100,
        )
        self.db.add(doc)
        self.db.flush()
        for idx, (pnum, txt) in enumerate(pages):
            self.db.add(
                DocumentChunk(
                    document_id=doc.id,
                    chunk_index=idx,
                    page_number=pnum,
                    content=txt,
                    embedding=generate_embedding(txt[:350]),
                )
            )
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def _run_analysis(self, doc_id: int, body: dict | None = None, headers: dict | None = None):
        payload = {"skip_llm": True, **(body or {})}
        return self.client.post(
            f"/documents/{doc_id}/research-analysis",
            json=payload,
            headers=headers if headers is not None else self.headers,
        )

    # 1. Paper detection
    def test_01_research_paper_detection_high_confidence(self):
        doc = self._seed_doc(self.user.id, "sample_upload.pdf", SAMPLE_PAPER_PAGES)
        res = self._run_analysis(doc.id)
        self.assertEqual(res.status_code, 200)
        det = res.json()["paper_detection"]
        self.assertTrue(det["is_research_paper"])
        self.assertGreaterEqual(det["confidence"], 0.75)
        self.assertIn("abstract", det["signals"])
        self.assertIn("methodology", det["signals"])
        self.assertIn("references", det["signals"])

    # 2. Non-paper detection (filename 'paper.pdf' must NOT trigger false positive!)
    def test_02_non_research_pdf_rejected_even_when_named_paper(self):
        resume_pages = [
            (
                1,
                "CAREER ASPIRATION\nSeeking a data science role in analytics.\n"
                "EDUCATIONAL QUALIFICATIONS\nMaster of Computer Applications, CGPA 9.2.\n"
                "INTERNSHIPS DONE\nData Science Intern working on dashboards.\n"
                "LANGUAGES KNOWN\nEnglish, Malayalam",
            )
        ]
        doc = self._seed_doc(self.user.id, "paper.pdf", resume_pages)
        res = self._run_analysis(doc.id)
        self.assertEqual(res.status_code, 200)
        det = res.json()["paper_detection"]
        self.assertFalse(det["is_research_paper"])
        self.assertLess(det["confidence"], 0.35)
        self.assertEqual(det["classification"], "non_research")

    # 3. Low-confidence / borderline technical document + manual classification override
    def test_03_borderline_technical_doc_and_manual_override(self):
        tech_report = [
            (
                1,
                "1. Introduction\nThis engineering report builds a handwritten OCR pipeline for document indexing.\n"
                "2. System Architecture\nModules include TrOCR line decoding, layout segmentation, and image preprocessing.\n"
                "We tested the pipeline on 44,582 sample lines and summarized deployment metrics in Table 1.\n",
            )
        ]
        doc = self._seed_doc(self.user.id, "project_report.docx", tech_report, doc_type="DOCX")
        res = self._run_analysis(doc.id)
        self.assertEqual(res.status_code, 200)
        det = res.json()["paper_detection"]
        self.assertFalse(det["is_research_paper"])
        self.assertGreaterEqual(det["confidence"], 0.25)

        # Manual override classifies it as research paper and persists override
        res_ovr = self._run_analysis(doc.id, {"classification_override": "research_paper"})
        self.assertEqual(res_ovr.status_code, 200)
        det_ovr = res_ovr.json()["paper_detection"]
        self.assertTrue(det_ovr["is_research_paper"])
        self.assertEqual(det_ovr["manual_override"], "research_paper")

    # 4. Title extraction
    def test_04_title_extraction_grounded(self):
        doc = self._seed_doc(self.user.id, "paper_a.pdf", SAMPLE_PAPER_PAGES)
        res = self._run_analysis(doc.id)
        title = res.json()["basic_information"]["title"]
        self.assertIn("Neural Graph Intrusion Detection", title["value"])
        self.assertEqual(title["fact_type"], "explicit")
        self.assertGreaterEqual(len(title["sources"]), 1)
        self.assertEqual(title["sources"][0]["page"], 1)

    # 5. Author extraction
    def test_05_author_extraction_grounded(self):
        doc = self._seed_doc(self.user.id, "paper_a.pdf", SAMPLE_PAPER_PAGES)
        res = self._run_analysis(doc.id)
        authors = res.json()["basic_information"]["authors"]
        self.assertIn("Priya Nair", authors["value"])
        self.assertEqual(authors["fact_type"], "explicit")
        self.assertEqual(authors["sources"][0]["page"], 1)

    # 6. Abstract extraction
    def test_06_abstract_extraction_grounded(self):
        doc = self._seed_doc(self.user.id, "paper_a.pdf", SAMPLE_PAPER_PAGES)
        res = self._run_analysis(doc.id)
        abstract = res.json()["basic_information"]["abstract"]
        self.assertIn("FlowGNN", abstract["value"])
        self.assertEqual(abstract["fact_type"], "explicit")
        self.assertGreaterEqual(len(abstract["sources"]), 1)

    # 7. Section extraction (hierarchy & ToC suppression)
    def test_07_section_hierarchy_extraction_and_toc_filtering(self):
        pages_with_toc = [
            (1, "Table of Contents\n1 Introduction . . . 2\n2 Methodology . . . 4\nAbstract\nShort summary paragraph explaining the objective and proposed architecture."),
            (2, "1. Introduction\nBackground on storage security.\n2. Methodology\n2.1 Dataset\nDataset has 50,000 samples."),
        ]
        doc = self._seed_doc(self.user.id, "thesis_outline.pdf", pages_with_toc)
        res = self._run_analysis(doc.id)
        sections = res.json()["sections"]
        titles = [s["title"] for s in sections]
        self.assertTrue(any("1. Introduction" in t for t in titles))
        meth_node = next((s for s in sections if "Methodology" in s["title"]), None)
        self.assertIsNotNone(meth_node)
        self.assertTrue(any("2.1 Dataset" in c["title"] for c in meth_node["children"]))
        self.assertFalse(any("..." in t for t in titles))

    # 8. Methodology extraction
    def test_08_methodology_extraction_grounded(self):
        doc = self._seed_doc(self.user.id, "paper_a.pdf", SAMPLE_PAPER_PAGES)
        res = self._run_analysis(doc.id)
        meth = res.json()["methodology"]
        self.assertIn("GraphSAGE", meth["architecture"]["value"])
        self.assertIn("PyTorch", meth["framework_tools"]["value"])
        self.assertEqual(meth["architecture"]["sources"][0]["page"], 2)

    # 9. Dataset extraction
    def test_09_dataset_and_size_extraction(self):
        doc = self._seed_doc(self.user.id, "paper_a.pdf", SAMPLE_PAPER_PAGES)
        res = self._run_analysis(doc.id)
        meth = res.json()["methodology"]
        self.assertIn("CICIDS-2017", meth["dataset"]["value"])
        self.assertIn("120,000", meth["dataset_size"]["value"])
        self.assertEqual(meth["dataset"]["sources"][0]["page"], 2)

    # 10. Metric extraction
    def test_10_metric_extraction_in_evaluation(self):
        doc = self._seed_doc(self.user.id, "paper_a.pdf", SAMPLE_PAPER_PAGES)
        res = self._run_analysis(doc.id)
        ev = res.json()["evaluation"]
        self.assertIn("Accuracy", ev["evaluation_metrics"]["value"])
        self.assertIn("96.4%", ev["numerical_findings"]["value"])

    # 11. Source evidence integrity
    def test_11_source_evidence_links_and_coverage(self):
        doc = self._seed_doc(self.user.id, "paper_a.pdf", SAMPLE_PAPER_PAGES)
        res = self._run_analysis(doc.id)
        data = res.json()
        self.assertGreaterEqual(data["evidence_coverage"], 0.99)
        self.assertGreater(len(data["evidence"]), 5)
        for ev in data["evidence"].values():
            self.assertEqual(ev["source"]["document_id"], doc.id)
            self.assertIsNotNone(ev["source"]["chunk_id"])
            self.assertGreaterEqual(ev["source"]["page"], 1)
            self.assertTrue(len(ev["source"]["excerpt"]) > 10)
            self.assertIn(ev["fact_type"], {"explicit", "derived", "inferred"})

    # 12. Missing field handling (must NOT fabricate!)
    def test_12_missing_fields_never_fabricated(self):
        minimal_pages = [
            (1, "Minimal Study on Sorting Speed\nAbstract\nWe measure bubble sort runtime on 500 integers in C++."),
        ]
        doc = self._seed_doc(self.user.id, "minimal.pdf", minimal_pages)
        res = self._run_analysis(doc.id)
        data = res.json()
        self.assertEqual(data["research_context"]["hypothesis"]["value"], MISSING_FIELD_TEXT)
        self.assertEqual(data["research_context"]["hypothesis"]["fact_type"], "missing")
        self.assertEqual(data["conclusion"]["limitations"]["value"], MISSING_FIELD_TEXT)
        self.assertEqual(data["conclusion"]["future_work"]["sources"], [])

    # 13. Ollama failure fallback
    def test_13_ollama_failure_falls_back_gracefully(self):
        doc = self._seed_doc(self.user.id, "paper_a.pdf", SAMPLE_PAPER_PAGES)
        with patch(
            "app.services.research.paper_extraction_service.query_ollama_json",
            side_effect=OllamaError("Connection refused"),
        ):
            res = self.client.post(
                f"/documents/{doc.id}/research-analysis",
                json={"skip_llm": False},
                headers=self.headers,
            )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["analysis_mode"], "deterministic_fallback")
        self.assertEqual(data["status"], "completed")
        self.assertTrue(data["paper_detection"]["is_research_paper"])

    # 14. Cache reuse
    def test_14_cache_reuse_on_repeat_post_and_get(self):
        doc = self._seed_doc(self.user.id, "paper_a.pdf", SAMPLE_PAPER_PAGES)
        res1 = self._run_analysis(doc.id)
        self.assertEqual(res1.status_code, 200)
        self.assertFalse(res1.json()["cached"])

        res2 = self._run_analysis(doc.id)
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.json()["cached"])
        self.assertFalse(res2.json()["is_outdated"])

        res_get = self.client.get(f"/documents/{doc.id}/research-analysis", headers=self.headers)
        self.assertEqual(res_get.status_code, 200)
        self.assertTrue(res_get.json()["cached"])
        self.assertEqual(res_get.json()["content_hash"], res1.json()["content_hash"])

    # 15. Content-hash invalidation
    def test_15_content_hash_invalidation_recomputes_when_document_changes(self):
        doc = self._seed_doc(self.user.id, "paper_a.pdf", SAMPLE_PAPER_PAGES)
        res1 = self._run_analysis(doc.id)
        hash1 = res1.json()["content_hash"]

        # Modify chunk content (e.g., re-OCR / document update)
        chunk = self.db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).first()
        chunk.content = chunk.content + "\nUpdated methodology adds differential privacy."
        self.db.commit()

        # GET reports outdated before recompute
        res_get = self.client.get(f"/documents/{doc.id}/research-analysis", headers=self.headers)
        self.assertTrue(res_get.json()["is_outdated"])

        # POST automatically invalidates and recomputes with new content_hash
        res2 = self._run_analysis(doc.id)
        self.assertFalse(res2.json()["cached"])
        self.assertNotEqual(res2.json()["content_hash"], hash1)

    # 16. Tenant isolation & JWT protection
    def test_16_tenant_isolation_and_auth_boundaries(self):
        doc = self._seed_doc(self.user.id, "private_paper.pdf", SAMPLE_PAPER_PAGES)
        self._run_analysis(doc.id)

        res_unauth = self.client.post(f"/documents/{doc.id}/research-analysis")
        self.assertEqual(res_unauth.status_code, 401)

        res_cross_post = self._run_analysis(doc.id, headers=self.other_headers)
        self.assertEqual(res_cross_post.status_code, 404)

        res_cross_get = self.client.get(
            f"/documents/{doc.id}/research-analysis", headers=self.other_headers
        )
        self.assertEqual(res_cross_get.status_code, 404)

        res_missing = self._run_analysis(999999)
        self.assertEqual(res_missing.status_code, 404)

    # 17. Malformed LLM JSON recovery & anti-hallucination filter
    def test_17_malformed_llm_json_and_ungrounded_llm_claims_rejected(self):
        doc = self._seed_doc(self.user.id, "paper_a.pdf", SAMPLE_PAPER_PAGES)
        # First test completely broken JSON output triggers safe fallback
        with patch(
            "app.services.research.paper_extraction_service.query_ollama_json",
            side_effect=ValueError("Could not parse valid JSON"),
        ):
            res_bad = self.client.post(
                f"/documents/{doc.id}/research-analysis",
                json={"skip_llm": False, "force_refresh": True},
                headers=self.headers,
            )
        self.assertEqual(res_bad.status_code, 200)
        self.assertEqual(res_bad.json()["analysis_mode"], "deterministic_fallback")

        # Next test hallucinated claim returned by Ollama is REJECTED because no chunk supports it
        hallucinated_payload = {
            "research_context": {
                "hypothesis": {
                    "value": "Quantum teleportation doubles satellite throughput to 999 Tbps.",
                    "chunk_id": 9999,
                    "fact_type": "explicit",
                }
            }
        }
        with patch(
            "app.services.research.paper_extraction_service.query_ollama_json",
            return_value=hallucinated_payload,
        ):
            res_hal = self.client.post(
                f"/documents/{doc.id}/research-analysis",
                json={"skip_llm": False, "force_refresh": True},
                headers=self.headers,
            )
        self.assertEqual(res_hal.status_code, 200)
        self.assertEqual(
            res_hal.json()["research_context"]["hypothesis"]["value"],
            MISSING_FIELD_TEXT,
        )

    # 18. Numerical extraction (explicit + derived deltas)
    def test_18_numerical_extraction_preserves_units_and_derives_deltas(self):
        doc = self._seed_doc(self.user.id, "paper_a.pdf", SAMPLE_PAPER_PAGES)
        res = self._run_analysis(doc.id)
        nums = res.json()["numerical_data"]
        self.assertTrue(any(n["original_value"] == "96.4%" and n["source"]["page"] == 3 for n in nums))
        self.assertTrue(any(n["original_value"] == "4.5 ms" for n in nums))
        self.assertTrue(any(n["metric_name"] == "Derived Accuracy Delta" and n["fact_type"] == "derived" and "4.2 percentage points" in n["original_value"] for n in nums))

    # 19. Table & figure reference preservation
    def test_19_table_figure_algorithm_equation_references_preserved(self):
        doc = self._seed_doc(self.user.id, "paper_a.pdf", SAMPLE_PAPER_PAGES)
        res = self._run_analysis(doc.id)
        tf = res.json()["tables_and_figures"]
        labels = {item["label"] for item in tf["items"]}
        self.assertIn("Table 1", labels)
        self.assertIn("Figure 2", labels)
        self.assertIn("Algorithm 1", labels)
        self.assertIn("Equation 1", labels)
        self.assertIn("not parsed", tf["visual_parsing_limitation"].lower())
        self.assertTrue(all(item["visually_parsed"] is False for item in tf["items"]))

    # 20. Handwritten / nonstandard document safety
    def test_20_handwritten_and_empty_documents_handled_safely(self):
        hw_doc = Document(
            user_id=self.user.id,
            filename="notes.png",
            document_type="HANDWRITTEN",
            file_path="uploads/notes.png",
            extracted_text="raw note text",
            text_length=13,
            is_handwritten=True,
            processing_status="completed",
            processing_progress=100,
        )
        self.db.add(hw_doc)
        self.db.flush()
        self.db.add(
            HandwrittenPage(
                document_id=hw_doc.id,
                page_number=1,
                original_image_path="uploads/notes_p1.png",
                raw_transcription="noisy text",
                edited_transcription="TCP uses SYN and SYN-ACK for reliable handshakes.",
                status="completed",
            )
        )
        empty_doc = self._seed_doc(self.user.id, "empty.txt", [(1, "   ")], doc_type="TXT")
        self.db.commit()

        res_hw = self._run_analysis(hw_doc.id)
        self.assertEqual(res_hw.status_code, 200)
        self.assertFalse(res_hw.json()["paper_detection"]["is_research_paper"])
        # Content hash incorporates edited handwritten transcription cleanly
        hw_row = self.db.query(HandwrittenPage).filter(HandwrittenPage.document_id == hw_doc.id).first()
        hw_row.edited_transcription = "TCP uses SYN, SYN-ACK, and ACK packets."
        self.db.commit()
        res_hw2 = self._run_analysis(hw_doc.id)
        self.assertNotEqual(res_hw.json()["content_hash"], res_hw2.json()["content_hash"])

        res_empty = self._run_analysis(empty_doc.id)
        self.assertEqual(res_empty.status_code, 200)
        self.assertFalse(res_empty.json()["paper_detection"]["is_research_paper"])

    # --- Phase 1 Hardening + Edge-Case Validation Tests (21-37) ---

    def test_21_bounded_llm_context_and_running_header_deduplication(self):
        from app.services.research.paper_extraction_service import (
            MAX_LLM_CONTEXT_CHARS,
            _select_bounded_evidence_packet,
        )
        from app.services.research.paper_section_service import ChunkUnit

        filler = "Encrypted flow graph modeling sentence with experimental validation. " * 25
        units = []
        for p in range(1, 10):
            header = "IEEE TRANSACTIONS ON INFORMATION FORENSICS, VOL. 19"
            footer = f"Authorized licensed use limited to IEEE University   Page {p}"
            if p == 1:
                body = "Abstract\nWe propose FlowShield for low-latency encrypted anomaly detection."
                role = "abstract"
            elif p == 2:
                body = "1. Introduction\nModern enterprise traffic requires privacy-preserving inspection."
                role = "introduction"
            elif p == 3:
                body = "2. Methodology\nWe train a 2-layer GAT encoder over packet burst graphs.\n" + filler
                role = "methodology"
            elif p == 4:
                body = "3. Experiments and Results\nAccuracy = 94.6% with latency = 3.2 ms.\n" + filler
                role = "results"
            elif p == 5:
                body = "Related Work . . . . . . . . . . . . . . . 12\nMethodology . . . . . . . . . . . . . . . . 18"
                role = "other"
            elif p == 8:
                body = "4. Conclusion\nFlowShield achieves reliable classification.\n" + filler
                role = "conclusion"
            else:
                body = f"Appendix Note {p}\n" + filler
                role = "appendix"
            units.append(
                ChunkUnit(
                    chunk_id=p,
                    chunk_index=p - 1,
                    page=p,
                    content=f"{header}\n{body}\n{footer}",
                    normalized_role=role,
                )
            )

        packet = _select_bounded_evidence_packet(units, max_chars=MAX_LLM_CONTEXT_CHARS)
        self.assertLessEqual(len(packet), MAX_LLM_CONTEXT_CHARS)
        self.assertNotIn("IEEE TRANSACTIONS ON INFORMATION FORENSICS", packet)
        self.assertNotIn("Authorized licensed use limited", packet)
        self.assertNotIn(". . . .", packet)
        self.assertIn("FlowShield", packet)
        self.assertLess(packet.find("Abstract"), packet.find("3. Experiments and Results"))

    def test_22_ollama_timeout_triggers_graceful_deterministic_fallback_and_bounded_opts(self):
        doc = self._seed_doc(self.user.id, "timeout_paper.pdf", SAMPLE_PAPER_PAGES)
        captured_kwargs = {}

        def _fake_timeout(*args, **kwargs):
            captured_kwargs.update(kwargs)
            raise OllamaError("Ollama request timed out after 35s")

        with patch("app.services.research.paper_extraction_service.query_ollama_json", side_effect=_fake_timeout):
            res = self._run_analysis(doc.id, body={"skip_llm": False, "force_refresh": True})

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["analysis_mode"], "deterministic_fallback")
        self.assertEqual(captured_kwargs.get("timeout"), 35)
        self.assertLessEqual(captured_kwargs.get("num_ctx", 99999), 4096)
        self.assertLessEqual(captured_kwargs.get("num_predict", 99999), 600)
        self.assertIn("FlowGNN", data["methodology"]["proposed_approach"]["value"])

    def test_23_ollama_empty_response_falls_back_gracefully(self):
        doc = self._seed_doc(self.user.id, "empty_llm.pdf", SAMPLE_PAPER_PAGES)
        with patch("app.services.research.paper_extraction_service.query_ollama_json", return_value={}):
            res = self._run_analysis(doc.id, body={"skip_llm": False, "force_refresh": True})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("FlowGNN", data["methodology"]["proposed_approach"]["value"])
        self.assertIn("CICIDS-2017", data["methodology"]["dataset"]["value"])

    def test_24_toc_filtering_spaced_dots_roman_numerals_and_collapsed_thesis_toc(self):
        from app.services.research.paper_section_service import is_toc_chunk, is_toc_line

        self.assertTrue(is_toc_line("1. Introduction . . . . . . . . . . . . . 1"))
        self.assertTrue(is_toc_line("List of Figures . . . . . . . . . . . . . . iv"))
        self.assertTrue(is_toc_line("Chapter 3 Methodology .................... 42"))
        self.assertTrue(is_toc_line("1.2 Problem Formulation   7", in_toc_block=True))
        collapsed_toc = (
            "Table of Contents\n"
            "28 2.6 Limitations of Traditional Access Control . . . . . . . . . . . . . 29 "
            "3. Proposed Framework 30 3.1 Key Management Services . . . . . . . . . . . 30 "
            "3.2 Decentralized Policy Engine . . . . . . . . . . . . . . . . . . . . 34"
        )
        self.assertTrue(is_toc_chunk(collapsed_toc))
        self.assertFalse(is_toc_line("Our proposed TLS 1.3 detector achieved 94.2% precision across 50,000 sessions."))
        self.assertFalse(is_toc_chunk("Section 3.1 describes our key management protocol and achieves 96.1% recall."))

        pages = [
            (1, collapsed_toc),
            *[(p + 1, txt) for p, txt in SAMPLE_PAPER_PAGES],
        ]
        doc = self._seed_doc(self.user.id, "thesis_with_toc.pdf", pages)
        res = self._run_analysis(doc.id)
        self.assertEqual(res.status_code, 200)
        dumped = json.dumps(res.json())
        self.assertNotIn("Key Management Services", dumped)
        self.assertNotIn("Decentralized Policy Engine", dumped)

    def test_25_ieee_two_column_style_paper_headers_and_authors_extracted(self):
        ieee_pages = [
            (
                1,
                "PacketGuard: Line-Rate DDoS Mitigation in Programmable Switches\n"
                "Rohan Kulkarni, Meera Krishnan, David Zhao\n"
                "Dept. of Electrical Engineering, Stanford University\n"
                "DOI: 10.1109/TON.2025.998877\n"
                "Abstract—Software-defined switches struggle under volumetric SYN floods [1]. "
                "We propose PacketGuard, a P4 stateful sketch pipeline for sub-millisecond mitigation.\n"
                "Index Terms—P4, DDoS Mitigation, Programmable Data Plane, Sketching\n"
                "978-1-6654-1234-5/25/$31.00 ©2025 IEEE\n"
                "I. INTRODUCTION\n"
                "Volumetric floods exhaust switch TCAM tables within seconds [2]. "
                "Our objective is bounded-memory SYN tracking at 100 Gbps line rate.",
            ),
            (
                2,
                "II. METHODOLOGY\n"
                "A. Threat Model\n"
                "We consider spoofed SYN floods originating from distributed botnets.\n"
                "B. Sketch Data Structure\n"
                "We conduct an experimental evaluation implemented in P4_16 on Intel Tofino.\n"
                "Evaluated on the CAIDA-2019 trace dataset containing 500,000 packets.",
            ),
            (
                3,
                "III. EXPERIMENTAL RESULTS\n"
                "As shown in Fig. 2(a) and Table II, PacketGuard achieves Precision = 97.4%, Recall = 96.1%, "
                "and F1-score = 96.7%, whereas Count-Min Sketch drops to 88.5% precision.\n"
                "IV. CONCLUSION\n"
                "PacketGuard maintains line-rate mitigation without external controller stalls.\n"
                "References\n"
                "[1] Liu Z. et al., NitroSketch, SIGCOMM 2019.",
            ),
        ]
        doc = self._seed_doc(self.user.id, "ieee_packetguard.pdf", ieee_pages)
        res = self._run_analysis(doc.id)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["paper_detection"]["is_research_paper"])
        self.assertEqual(data["paper_detection"]["classification"], "research_paper")
        authors_txt = data["basic_information"]["authors"]["value"]
        self.assertIn("Rohan Kulkarni", authors_txt)

        def _collect_titles(nodes):
            out = []
            for n in nodes:
                out.append(n["title"])
                out.extend(_collect_titles(n.get("children") or []))
            return out

        titles = _collect_titles(data["sections"])
        self.assertTrue(any("INTRODUCTION" in t for t in titles))
        self.assertTrue(any("Threat Model" in t for t in titles))
        self.assertNotIn("©2025 IEEE", json.dumps(data["research_context"]))
        derived = [n for n in data["numerical_data"] if n["fact_type"] == "derived"]
        self.assertTrue(any("8.9" in n["original_value"] or "8.90" in n["original_value"] for n in derived))

    def test_26_acm_ccs_paper_classification_and_metadata(self):
        acm_pages = [
            (
                1,
                "VeriSQL: Formally Verified Query Rewriting for Multi-Tenant Databases\n"
                "Elena Petrova, Marcus Vance\n"
                "Proceedings of ACM SIGMOD Conference (2025)\n"
                "ACM ISBN 979-8-4007-1111-2/25/06\n"
                "Abstract\n"
                "We present VeriSQL, an SMT-backed query optimizer that prevents tenant row leakage.\n"
                "CCS CONCEPTS\n"
                "• Security and privacy -> Database and storage security.\n"
                "Keywords: Formal Verification, Multi-Tenant Isolation, SMT",
            ),
            (
                2,
                "1 INTRODUCTION\n"
                "We formulate invariant synthesis over relational algebra trees.\n"
                "2 METHODOLOGY\n"
                "Our empirical study tests 1,200 TPC-C queries using Z3 solver in Python.",
            ),
            (
                3,
                "3 EVALUATION\n"
                "VeriSQL achieves Accuracy = 99.8% isolation soundness with latency = 1.8 ms (p < 0.01).\n"
                "4 CONCLUSION\n"
                "VeriSQL eliminates cross-tenant predicate bugs in production SQL engines.\n"
                "References\n"
                "[1] Wang S. et al., Cosette, CIDR 2017.",
            ),
        ]
        doc = self._seed_doc(self.user.id, "acm_verisql.pdf", acm_pages)
        res = self._run_analysis(doc.id)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["paper_detection"]["is_research_paper"])
        pub_val = data["basic_information"]["publication_info"]["value"]
        self.assertNotEqual(pub_val, MISSING_FIELD_TEXT)
        self.assertIn("ACM", pub_val)
        self.assertIn("Formal Verification", data["basic_information"]["keywords"]["value"])

    def test_27_structural_and_year_numbers_never_misclassified_as_results(self):
        trap_pages = [
            (
                1,
                "Evaluating Structural Number Isolation in Benchmark Pipelines\n"
                "Authors: Asha Verma, Kiran Rao\n"
                "Abstract\n"
                "We propose NumGuard to verify numeric reporting accuracy.\n"
                "1. Introduction\n"
                "See Section 3.2, Figure 4, Table 2, Page 12, Reference [18], and Eq. (5) for definitions published in 2024.",
            ),
            (
                2,
                "2. Methodology\n"
                "We run a quantitative experiment over 5,000 samples from GLUE.\n"
                "3. Results\n"
                "In Section 3.2 (published 2024), Reference [18] and Figure 4 describe the split, while our model reports "
                "Accuracy = 87.2%, F1-score = 0.91, p < 0.05, and 95% CI [0.88, 0.94] in Table 2.",
            ),
            (
                3,
                "4. Conclusion\n"
                "Careful metric parsing avoids false structural numbers.\n"
                "References\n"
                "[18] Smith J., Benchmark Standards, NeurIPS 2024.",
            ),
        ]
        doc = self._seed_doc(self.user.id, "structural_trap.pdf", trap_pages)
        res = self._run_analysis(doc.id)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        extracted_vals = [item["original_value"] for item in data["numerical_data"]]
        joined_vals = " | ".join(extracted_vals)
        for forbidden in ("3.2", "Page 12", "[18]", "2024", "Eq. (5)", "Figure 4", "Table 2"):
            self.assertNotIn(forbidden, joined_vals)
        self.assertTrue(any("87.2%" in v for v in extracted_vals))
        self.assertTrue(any("0.91" in v for v in extracted_vals))
        self.assertTrue(any("p < 0.05" in v.lower() for v in extracted_vals))
        self.assertTrue(any("0.88" in v and "0.94" in v for v in extracted_vals))

    def test_28_missing_limitations_future_work_and_publication_never_fabricated(self):
        minimal_pages = [
            (
                1,
                "Compact Routing in Edge Meshes\n"
                "Authors: Tarun Singh\n"
                "Abstract\n"
                "We propose MeshRoute to lower hop count in edge clusters.\n"
                "1. Introduction\n"
                "Static shortest-path routing causes tail latency spikes.\n",
            ),
            (
                2,
                "2. Methodology\n"
                "We evaluate MeshRoute using an experimental simulation.\n"
                "3. Conclusion\n"
                "MeshRoute simplifies routing convergence.\n"
                "References\n"
                "[1] Stoica I., Chord, SIGCOMM 2001.",
            ),
        ]
        doc = self._seed_doc(self.user.id, "minimal_paper.pdf", minimal_pages)
        res = self._run_analysis(doc.id)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["conclusion"]["limitations"]["value"], MISSING_FIELD_TEXT)
        self.assertEqual(data["conclusion"]["limitations"]["fact_type"], "missing")
        self.assertEqual(data["conclusion"]["future_work"]["value"], MISSING_FIELD_TEXT)
        self.assertEqual(data["basic_information"]["publication_info"]["value"], MISSING_FIELD_TEXT)
        self.assertEqual(data["research_context"]["hypothesis"]["value"], MISSING_FIELD_TEXT)

    def test_29_visual_references_roman_subfigures_and_equations_grounded_not_visually_parsed(self):
        vis_pages = [
            *SAMPLE_PAPER_PAGES[:2],
            (
                3,
                "3. Results\n"
                "Figure 3(a) plots throughput scaling while Table II compares per-flow memory usage.\n"
                "Eq. (4) bounds estimation error and Algorithm 2 details bucket eviction.\n"
                "Accuracy = 95.1% on CICIDS-2017.",
            ),
            SAMPLE_PAPER_PAGES[3],
        ]
        doc = self._seed_doc(self.user.id, "visual_refs.pdf", vis_pages)
        res = self._run_analysis(doc.id)
        self.assertEqual(res.status_code, 200)
        refs = res.json()["tables_and_figures"]["items"]
        labels = [r["label"] for r in refs]
        self.assertTrue(any("Figure 3(a)" in lbl for lbl in labels))
        self.assertTrue(any("Table II" in lbl for lbl in labels))
        self.assertTrue(any("Equation (4)" in lbl for lbl in labels))
        self.assertTrue(any("Algorithm 2" in lbl for lbl in labels))
        self.assertTrue(all(r["visually_parsed"] is False for r in refs))

    def test_30_student_assignment_rejected_as_non_research(self):
        assignment_pages = [
            (
                1,
                "CS-401 Operating Systems Assignment 3\n"
                "Student Name: Ananya Das | Roll Number: 22CS041 | Course Syllabus\n"
                "Homework Submission: Implement a round-robin scheduler in C.\n"
                "Abstract concepts from lectures were applied to write process queues.\n"
                "Problem Statement: Build a priority queue and run three test cases.",
            ),
            (
                2,
                "Implementation Notes\n"
                "We tested process switching using a sample driver script.",
            ),
        ]
        doc = self._seed_doc(self.user.id, "cs401_assignment.pdf", assignment_pages)
        res = self._run_analysis(doc.id)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["paper_detection"]["is_research_paper"])
        self.assertEqual(res.json()["paper_detection"]["classification"], "non_research")

    def test_31_business_and_product_documentation_rejected_as_non_research(self):
        product_pages = [
            (
                1,
                "Acme Cloud Gateway Enterprise Edition - User Manual & API Reference\n"
                "Installation Guide: Download the binary and configure your subscription plan.\n"
                "Executive Summary\n"
                "Quarterly Revenue grew 18% after enterprise customer onboarding.\n"
                "See SLA terms, pricing tiers, and troubleshooting steps for REST endpoints.",
            ),
        ]
        doc = self._seed_doc(self.user.id, "product_manual_api_ref.pdf", product_pages)
        res = self._run_analysis(doc.id)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["paper_detection"]["is_research_paper"])

    def test_32_handwritten_note_with_academic_keywords_clamped_unless_overridden(self):
        hw_academic_pages = [
            (
                1,
                "Lecture Notes on Abstract Algebra and Research Methodology\n"
                "References: Chapter 2, Exercise Set B, DOI: 10.1000/note.sample\n"
                "1. Introduction to groups and rings\n"
                "Evaluation of homework Accuracy = 90%",
            ),
        ]
        hw_doc = self._seed_doc(
            self.user.id,
            "lecture_notes_scan.png",
            hw_academic_pages,
            doc_type="HANDWRITTEN",
            is_hw=True,
        )
        res = self._run_analysis(hw_doc.id)
        self.assertEqual(res.status_code, 200)
        det = res.json()["paper_detection"]
        self.assertFalse(det["is_research_paper"])
        self.assertLessEqual(det["confidence"], 0.35)
        self.assertEqual(det["classification"], "non_research")
        res_override = self._run_analysis(
            hw_doc.id,
            body={"classification_override": "research_paper", "force_refresh": True},
        )
        self.assertEqual(res_override.status_code, 200)
        self.assertTrue(res_override.json()["paper_detection"]["is_research_paper"])
        self.assertEqual(res_override.json()["paper_detection"]["manual_override"], "research_paper")

    def test_33_evidence_drawer_metadata_supports_printed_and_handwritten_navigation(self):
        hw_doc = self._seed_doc(
            self.user.id,
            "notes_research.png",
            SAMPLE_PAPER_PAGES,
            doc_type="HANDWRITTEN",
            is_hw=True,
        )
        res = self._run_analysis(hw_doc.id, body={"classification_override": "research_paper"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["is_handwritten"])
        self.assertEqual(data["document_type"], "HANDWRITTEN")
        sources = data["basic_information"]["title"]["sources"]
        self.assertTrue(len(sources) >= 1)
        self.assertEqual(sources[0]["document_id"], hw_doc.id)
        self.assertEqual(sources[0]["page"], 1)

    def test_34_evidence_never_cites_toc_chunks(self):
        toc_first_page = (
            1,
            "Contents\n"
            "Abstract . . . . . . . . . . . . . . . . . . . 2\n"
            "1. Introduction . . . . . . . . . . . . . . . . 2\n"
            "2. Methodology . . . . . . . . . . . . . . . . 3\n"
            "3. Limitations and Future Work . . . . . . . . 4",
        )
        pages = [toc_first_page, *[(p + 1, txt) for p, txt in SAMPLE_PAPER_PAGES]]
        doc = self._seed_doc(self.user.id, "paper_with_leading_toc.pdf", pages)
        res = self._run_analysis(doc.id)
        self.assertEqual(res.status_code, 200)
        lim_sources = res.json()["conclusion"]["limitations"]["sources"]
        self.assertTrue(len(lim_sources) >= 1)
        self.assertTrue(all(". . . ." not in s["excerpt"] for s in lim_sources))
        self.assertEqual(lim_sources[0]["page"], 5)
        abs_sources = res.json()["basic_information"]["abstract"]["sources"]
        self.assertTrue(len(abs_sources) >= 1)
        self.assertTrue(all(". . . ." not in s["excerpt"] for s in abs_sources))
        self.assertEqual(abs_sources[0]["page"], 2)

    def test_35_invalid_document_id_and_missing_analysis_get_return_404(self):
        res_post = self._run_analysis(999999)
        self.assertEqual(res_post.status_code, 404)
        res_get = self.client.get("/documents/999999/research-analysis", headers=self.headers)
        self.assertEqual(res_get.status_code, 404)
        doc = self._seed_doc(self.user.id, "un_analyzed.pdf", SAMPLE_PAPER_PAGES)
        res_get_doc = self.client.get(f"/documents/{doc.id}/research-analysis", headers=self.headers)
        self.assertEqual(res_get_doc.status_code, 404)

    def test_36_non_research_override_persists_across_cached_get(self):
        doc = self._seed_doc(self.user.id, "override_persist.pdf", SAMPLE_PAPER_PAGES)
        res1 = self._run_analysis(doc.id, body={"classification_override": "non_research"})
        self.assertEqual(res1.status_code, 200)
        self.assertFalse(res1.json()["paper_detection"]["is_research_paper"])
        self.assertEqual(res1.json()["paper_detection"]["manual_override"], "non_research")

        res_get = self.client.get(f"/documents/{doc.id}/research-analysis", headers=self.headers)
        self.assertEqual(res_get.status_code, 200)
        self.assertFalse(res_get.json()["paper_detection"]["is_research_paper"])
        self.assertTrue(res_get.json()["cached"])

    def test_37_journal_article_keywords_and_doi_detected(self):
        journal_pages = [
            (
                1,
                "Adaptive Anomaly Scoring in IoT Telemetry Streams\n"
                "Authors: Dr. Kavita Joshi\n"
                "Journal of Network and Computer Applications, Vol. 214, Issue 3\n"
                "DOI: 10.1016/j.jnca.2025.103912\n"
                "Abstract\n"
                "We propose StreamScore to detect telemetry drift in constrained sensors.",
            ),
            *SAMPLE_PAPER_PAGES[1:],
        ]
        doc = self._seed_doc(self.user.id, "journal_paper.pdf", journal_pages)
        res = self._run_analysis(doc.id)
        self.assertEqual(res.status_code, 200)
        det = res.json()["paper_detection"]
        self.assertTrue(det["is_research_paper"])
        self.assertIn("publication_or_thesis_metadata", det["signals"])
        self.assertIn("10.1016/j.jnca.2025.103912", res.json()["basic_information"]["publication_info"]["value"])


if __name__ == "__main__":
    unittest.main()

