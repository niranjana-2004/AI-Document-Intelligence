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


if __name__ == "__main__":
    unittest.main()

