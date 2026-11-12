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
from app.models.knowledge_graph import (
    KnowledgeGraph,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    ensure_knowledge_graph_schema,
)
from app.models.research_paper_analysis import ResearchPaperAnalysis
from app.models.user import User
from app.schemas.knowledge_graph import ALLOWED_RELATIONSHIPS, normalize_relationship
from app.services.embedding_services import generate_embedding


NETWORKING_PAGES = [
    (
        1,
        "# TCP Attacks\n"
        "## SYN Flood\n"
        "SYN Flood is a Denial-of-Service (DoS) attack that exploits the TCP three-way handshake (SYN, SYN-ACK, ACK). "
        "During normal connections, the server allocates a Transmission Control Block (TCB) inside the Backlog Queue. "
        "The attacker sends spoofed SYN packets and never returns ACK, creating half-open connections. "
        "Therefore, SYN Flood exhausts Backlog Queue memory and degrades Server availability for genuine Client connections. "
        "Information, system, technology, stuff, and overview should not clutter key concepts.",
    ),
    (
        2,
        "## Defenses against SYN Flood\n"
        "SYN Cookies mitigates SYN Flood attacks by encoding connection state directly into the sequence number instead of allocating TCB immediately. "
        "Ingress filtering under BCP 38 blocks spoofed IP packets before they reach the Server. "
        "## TCP Session Hijacking\n"
        "TCP Session Hijacking is an attack that relies on sequence number prediction to take control of an active session.",
    ),
]


class KnowledgeGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=cls.engine)
        ensure_knowledge_graph_schema(cls.engine)
        cls.TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

    def setUp(self):
        self.db = self.TestingSessionLocal()
        self.db.query(KnowledgeGraphEdge).delete()
        self.db.query(KnowledgeGraphNode).delete()
        self.db.query(KnowledgeGraph).delete()
        self.db.query(ResearchPaperAnalysis).delete()
        self.db.query(HandwrittenPage).delete()
        self.db.query(DocumentChunk).delete()
        self.db.query(Document).delete()
        self.db.query(User).delete()
        self.db.commit()

        self.user_a = User(
            full_name="Alice",
            email="alice@example.com",
            password_hash=hash_password("secret123"),
            is_verified=True,
        )
        self.user_b = User(
            full_name="Bob",
            email="bob@example.com",
            password_hash=hash_password("secret123"),
            is_verified=True,
        )
        self.db.add_all([self.user_a, self.user_b])
        self.db.commit()
        self.db.refresh(self.user_a)
        self.db.refresh(self.user_b)

        self.headers_a = {
            "Authorization": f"Bearer {create_access_token({'sub': str(self.user_a.id)})}"
        }
        self.headers_b = {
            "Authorization": f"Bearer {create_access_token({'sub': str(self.user_b.id)})}"
        }

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    def _create_printed_doc(self, user_id, pages=NETWORKING_PAGES, filename="tcp_notes.pdf", doc_type="PDF"):
        full_text = "\n\n".join(text for _, text in pages)
        doc = Document(
            user_id=user_id,
            filename=filename,
            document_type=doc_type,
            file_path=f"uploads/{filename}",
            extracted_text=full_text,
            text_length=len(full_text),
            is_handwritten=False,
            processing_status="completed",
            processing_progress=100,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        for idx, (page_num, content) in enumerate(pages):
            self.db.add(
                DocumentChunk(
                    document_id=doc.id,
                    chunk_index=idx,
                    page_number=page_num,
                    category="body",
                    content=content,
                    embedding=generate_embedding(content),
                )
            )
        self.db.commit()
        return doc

    def _create_handwritten_doc(self, user_id, pages):
        full_text = "\n\n".join(p["raw"] for p in pages)
        doc = Document(
            user_id=user_id,
            filename="hw_networks.pdf",
            document_type="HANDWRITTEN",
            file_path="uploads/hw_networks.pdf",
            extracted_text=full_text,
            text_length=len(full_text),
            is_handwritten=True,
            processing_status="completed",
            processing_progress=100,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        for p in pages:
            self.db.add(
                HandwrittenPage(
                    document_id=doc.id,
                    page_number=p["page"],
                    original_image_path=f"uploads/hw_p{p['page']}.png",
                    raw_transcription=p["raw"],
                    edited_transcription=p.get("edited"),
                    confidence_score=0.86,
                )
            )
        self.db.commit()
        return doc

    def test_01_authentication_required(self):
        doc = self._create_printed_doc(self.user_a.id)
        for method, url in [
            ("post", f"/documents/{doc.id}/knowledge-graph"),
            ("get", f"/documents/{doc.id}/knowledge-graph"),
            ("delete", f"/documents/{doc.id}/knowledge-graph"),
            ("post", f"/documents/{doc.id}/knowledge-graph/regenerate"),
        ]:
            res = getattr(self.client, method)(url)
            self.assertEqual(res.status_code, 401)

    def test_02_ownership_isolation(self):
        doc = self._create_printed_doc(self.user_a.id)
        self.assertEqual(
            self.client.post(f"/documents/{doc.id}/knowledge-graph", json={"skip_llm": True}, headers=self.headers_a).status_code,
            200,
        )
        for method, url in [
            ("get", f"/documents/{doc.id}/knowledge-graph"),
            ("post", f"/documents/{doc.id}/knowledge-graph"),
            ("delete", f"/documents/{doc.id}/knowledge-graph"),
            ("post", f"/documents/{doc.id}/knowledge-graph/regenerate"),
        ]:
            res = getattr(self.client, method)(url, headers=self.headers_b)
            self.assertEqual(res.status_code, 404)

    def test_03_missing_document_returns_404(self):
        res = self.client.post("/documents/999999/knowledge-graph", json={"skip_llm": True}, headers=self.headers_a)
        self.assertEqual(res.status_code, 404)

    def test_04_vocabulary_normalization_rejects_arbitrary_verbs(self):
        self.assertEqual(normalize_relationship("exploits"), "depends_on")
        self.assertEqual(normalize_relationship("mitigates"), "contradicts")
        self.assertEqual(normalize_relationship("leads to"), "results_in")
        self.assertIsNone(normalize_relationship("magically_teleports"))
        self.assertIsNone(normalize_relationship("hallucinated_verb"))

    def test_05_node_extraction_and_grounding_printed_pdf(self):
        doc = self._create_printed_doc(self.user_a.id)
        res = self.client.post(
            f"/documents/{doc.id}/knowledge-graph",
            json={"skip_llm": True},
            headers=self.headers_a,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreaterEqual(len(data["nodes"]), 4)
        self.assertEqual(data["stats"]["grounded_node_ratio"], 1.0)
        labels = [n["label"].lower() for n in data["nodes"]]
        self.assertTrue(any("syn flood" in l for l in labels))
        for n in data["nodes"]:
            self.assertTrue(len(n["evidence"]) >= 1)
            self.assertTrue(all(ev["page"] in (1, 2) for ev in n["evidence"]))

    def test_06_generic_filler_terms_filtered(self):
        doc = self._create_printed_doc(self.user_a.id)
        res = self.client.post(f"/documents/{doc.id}/knowledge-graph", json={"skip_llm": True}, headers=self.headers_a)
        labels_lower = {n["label"].lower() for n in res.json()["nodes"]}
        for banned in ("information", "system", "technology", "stuff", "overview"):
            self.assertNotIn(banned, labels_lower)

    def test_07_deduplication_and_aliases_merged(self):
        doc = self._create_printed_doc(self.user_a.id)
        res = self.client.post(f"/documents/{doc.id}/knowledge-graph", json={"skip_llm": True}, headers=self.headers_a)
        nodes = res.json()["nodes"]
        dos_nodes = [n for n in nodes if "denial" in n["label"].lower() or "dos" in [a.lower() for a in n["aliases"]] or n["label"].upper() == "DOS"]
        self.assertLessEqual(len(dos_nodes), 1)
        if dos_nodes:
            combined = [dos_nodes[0]["label"].lower(), *[a.lower() for a in dos_nodes[0]["aliases"]]]
            self.assertTrue("dos" in combined)

    def test_08_complementary_terms_not_over_merged(self):
        pages = [
            (
                1,
                "Client sends SYN packets to Server during TCP handshake.\n"
                "Precision measures positive predictive value while Recall measures sensitivity cleanly across datasets.\n"
                "Client communicates with Server and Server allocates TCB for Client requests.\n"
                "Precision and Recall trade off in imbalanced classification.",
            )
        ]
        doc = self._create_printed_doc(self.user_a.id, pages=pages)
        res = self.client.post(f"/documents/{doc.id}/knowledge-graph", json={"skip_llm": True}, headers=self.headers_a)
        labels = {n["label"].lower() for n in res.json()["nodes"]}
        self.assertIn("precision", labels)
        self.assertIn("recall", labels)

    def test_09_toc_noise_filtered(self):
        pages = [
            (1, "Table of Contents\n1. Introduction ............ 2\n2. Methodology ............ 4\n3. Conclusion ............ 8"),
            NETWORKING_PAGES[0],
        ]
        doc = self._create_printed_doc(self.user_a.id, pages=pages)
        res = self.client.post(f"/documents/{doc.id}/knowledge-graph", json={"skip_llm": True}, headers=self.headers_a)
        for node in res.json()["nodes"]:
            for ev in node["evidence"]:
                self.assertNotIn("............", ev["excerpt"])

    def test_10_controlled_relationships_and_no_self_loops(self):
        doc = self._create_printed_doc(self.user_a.id)
        res = self.client.post(
            f"/documents/{doc.id}/knowledge-graph",
            json={"skip_llm": True, "include_low_confidence": True},
            headers=self.headers_a,
        )
        edges = res.json()["edges"]
        self.assertGreaterEqual(len(edges), 2)
        seen_keys = set()
        for e in edges:
            self.assertIn(e["relationship"], ALLOWED_RELATIONSHIPS)
            self.assertNotEqual(e["source_key"], e["target_key"])
            self.assertTrue(len(e["evidence"]) >= 1)
            k = (e["source_key"], e["relationship"], e["target_key"])
            self.assertNotIn(k, seen_keys)
            seen_keys.add(k)

    def test_11_confidence_tiers_and_default_low_filter(self):
        # Craft multi-sentence chunk spanning weak co-occurrence + explicit same-sentence link
        pages = [
            (
                1,
                "SYN Flood exploits TCP Handshake directly.\n"
                "Alpha Protocol initializes packets sequentially.\n"
                "Beta Queue waits asynchronously.\n"
                "Gamma Filter inspects headers later in the pipeline.",
            )
        ]
        doc = self._create_printed_doc(self.user_a.id, pages=pages)
        res_default = self.client.post(
            f"/documents/{doc.id}/knowledge-graph",
            json={"skip_llm": True, "include_low_confidence": False},
            headers=self.headers_a,
        ).json()
        res_all = self.client.get(
            f"/documents/{doc.id}/knowledge-graph?include_low_confidence=true",
            headers=self.headers_a,
        ).json()
        for e in res_default["edges"]:
            self.assertGreaterEqual(e["confidence"], 0.50)
            self.assertIn("evidence_count_score", e["confidence_breakdown"])
        self.assertGreaterEqual(len(res_all["edges"]), len(res_default["edges"]))

    def test_12_origin_tracking_explicit_vs_derived(self):
        doc = self._create_printed_doc(self.user_a.id)
        res = self.client.post(
            f"/documents/{doc.id}/knowledge-graph",
            json={"skip_llm": True, "include_low_confidence": True},
            headers=self.headers_a,
        ).json()
        origins = {e["origin"] for e in res["edges"]}
        self.assertIn("explicit", origins)

    def test_13_llm_mocked_verification_refines_relationship(self):
        doc = self._create_printed_doc(self.user_a.id)

        def fake_llm(prompt, system_prompt="", **kwargs):
            return {
                "relations": [
                    {
                        "source": "SYN Flood",
                        "target": "Backlog Queue",
                        "relationship": "exhausts",
                        "reason": "Explicitly stated in page 1 text.",
                    }
                ]
            }

        with patch("app.services.knowledge_graph_relationship_service.query_ollama_json", side_effect=fake_llm):
            res = self.client.post(
                f"/documents/{doc.id}/knowledge-graph",
                json={"skip_llm": False},
                headers=self.headers_a,
            )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["generation_method"], "hybrid")
        self.assertGreaterEqual(data["diagnostics"]["llm_verified_count"], 1)
        for e in data["edges"]:
            self.assertIn(e["relationship"], ALLOWED_RELATIONSHIPS)

    def test_14_llm_hallucinated_entities_and_bad_verbs_rejected(self):
        doc = self._create_printed_doc(self.user_a.id)

        def fake_bad_llm(prompt, system_prompt="", **kwargs):
            return {
                "relations": [
                    {
                        "source": "Quantum Unicorn",
                        "target": "SYN Flood",
                        "relationship": "uses",
                        "reason": "Hallucinated entity",
                    },
                    {
                        "source": "SYN Flood",
                        "target": "SYN Cookies",
                        "relationship": "magically_destroys",
                        "reason": "Invalid verb",
                    },
                ]
            }

        with patch("app.services.knowledge_graph_relationship_service.query_ollama_json", side_effect=fake_bad_llm):
            res = self.client.post(
                f"/documents/{doc.id}/knowledge-graph",
                json={"skip_llm": False},
                headers=self.headers_a,
            ).json()

        labels = {n["label"] for n in res["nodes"]}
        self.assertNotIn("Quantum Unicorn", labels)
        for e in res["edges"]:
            self.assertIn(e["relationship"], ALLOWED_RELATIONSHIPS)
        self.assertGreaterEqual(res["diagnostics"]["llm_rejected_ungrounded"], 1)
        self.assertGreaterEqual(res["diagnostics"]["rejected_invalid_relationships"], 1)

    def test_15_llm_offline_timeout_graceful_fallback(self):
        doc = self._create_printed_doc(self.user_a.id)
        with patch(
            "app.services.knowledge_graph_relationship_service.query_ollama_json",
            side_effect=RuntimeError("Ollama connection refused"),
        ):
            res = self.client.post(
                f"/documents/{doc.id}/knowledge-graph",
                json={"skip_llm": False},
                headers=self.headers_a,
            )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ready")
        self.assertGreaterEqual(data["diagnostics"]["llm_fallback_used"], 1)

    def test_16_sqlite_persistence_and_cache_hit(self):
        doc = self._create_printed_doc(self.user_a.id)
        first = self.client.post(
            f"/documents/{doc.id}/knowledge-graph",
            json={"skip_llm": True},
            headers=self.headers_a,
        ).json()
        self.assertFalse(first["cached"])

        second = self.client.post(
            f"/documents/{doc.id}/knowledge-graph",
            json={"skip_llm": True},
            headers=self.headers_a,
        ).json()
        self.assertTrue(second["cached"])
        self.assertEqual(second["content_hash"], first["content_hash"])

        fetched = self.client.get(f"/documents/{doc.id}/knowledge-graph", headers=self.headers_a).json()
        self.assertTrue(fetched["cached"])
        self.assertFalse(fetched["is_outdated"])

    def test_17_regenerate_replaces_snapshot_cleanly(self):
        doc = self._create_printed_doc(self.user_a.id)
        self.client.post(f"/documents/{doc.id}/knowledge-graph", json={"skip_llm": True}, headers=self.headers_a)
        regen = self.client.post(
            f"/documents/{doc.id}/knowledge-graph/regenerate",
            json={"skip_llm": True},
            headers=self.headers_a,
        )
        self.assertEqual(regen.status_code, 200)
        self.assertFalse(regen.json()["cached"])
        self.assertEqual(
            self.db.query(KnowledgeGraph).filter(KnowledgeGraph.document_id == doc.id).count(),
            1,
        )

    def test_18_content_hash_invalidation_on_printed_chunk_edit(self):
        doc = self._create_printed_doc(self.user_a.id)
        first = self.client.post(
            f"/documents/{doc.id}/knowledge-graph",
            json={"skip_llm": True},
            headers=self.headers_a,
        ).json()

        chunk = self.db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).first()
        chunk.content += "\nBGP Hijacking exploits routing announcements."
        self.db.commit()

        check_get = self.client.get(f"/documents/{doc.id}/knowledge-graph", headers=self.headers_a).json()
        self.assertTrue(check_get["is_outdated"])

        rebuilt = self.client.post(
            f"/documents/{doc.id}/knowledge-graph",
            json={"skip_llm": True},
            headers=self.headers_a,
        ).json()
        self.assertFalse(rebuilt["cached"])
        self.assertNotEqual(rebuilt["content_hash"], first["content_hash"])

    def test_19_handwritten_document_uses_edited_transcription_and_invalidates(self):
        doc = self._create_handwritten_doc(
            self.user_a.id,
            pages=[
                {
                    "page": 1,
                    "raw": "SYN Flood abuses TCP Handshake backlog queue.",
                    "edited": "SYN Flood exploits TCP three-way handshake and SYN Cookies mitigates SYN Flood reliably.",
                }
            ],
        )
        first = self.client.post(
            f"/documents/{doc.id}/knowledge-graph",
            json={"skip_llm": True},
            headers=self.headers_a,
        ).json()
        self.assertTrue(first["is_handwritten"])
        labels = {n["label"].lower() for n in first["nodes"]}
        self.assertTrue(any("syn cookies" in l for l in labels))

        # Editing transcription marks cached graph outdated
        hw_page = self.db.query(HandwrittenPage).filter(HandwrittenPage.document_id == doc.id).first()
        hw_page.edited_transcription += "\nRate Limiting prevents excessive half-open packets."
        self.db.commit()

        check_get = self.client.get(f"/documents/{doc.id}/knowledge-graph", headers=self.headers_a).json()
        self.assertTrue(check_get["is_outdated"])

    def test_20_research_paper_enrichment_and_typed_nodes(self):
        pages = [
            (
                1,
                "Abstract\nEncrypted Traffic Classification suffers from flow obfuscation. "
                "We propose FlowGNN, evaluated on CICIDS-2017 using F1-Score.",
            ),
            (
                2,
                "Methodology and Results\nFlowGNN outperforms Baseline CNN on CICIDS-2017 and improves F1-Score by 8%.",
            ),
        ]
        doc = self._create_printed_doc(self.user_a.id, pages=pages, filename="flowgnn_paper.pdf")
        rpa = ResearchPaperAnalysis(
            user_id=self.user_a.id,
            document_id=doc.id,
            content_hash="abc123",
            paper_detection={"is_research_paper": True},
            basic_information={"title": "FlowGNN"},
            research_context={"problem_statement": ["Encrypted Traffic Classification"]},
            methodology={"proposed_method": ["FlowGNN"], "datasets": ["CICIDS-2017"]},
            evaluation={"metrics": ["F1-Score"], "baselines": ["Baseline CNN"], "datasets": ["CICIDS-2017"]},
            conclusion={"limitations": []},
            sections=[],
            numerical_data=[],
            tables_and_figures=[],
            evidence={},
            timings={},
        )
        self.db.add(rpa)
        self.db.commit()

        res = self.client.post(f"/documents/{doc.id}/knowledge-graph", json={"skip_llm": True}, headers=self.headers_a).json()
        self.assertTrue(res["stats"]["used_research_analysis"])
        types_by_label = {n["label"]: n["node_type"] for n in res["nodes"]}
        self.assertEqual(types_by_label.get("FlowGNN"), "Method")
        self.assertEqual(types_by_label.get("CICIDS-2017"), "Dataset")
        self.assertEqual(types_by_label.get("F1-Score"), "Metric")

    def test_21_mixed_printed_and_handwritten_document(self):
        doc = Document(
            user_id=self.user_a.id,
            filename="mixed_lecture.pdf",
            document_type="PDF",
            file_path="uploads/mixed_lecture.pdf",
            extracted_text="TCP Handshake overview",
            text_length=24,
            is_handwritten=False,
            processing_status="completed",
            processing_progress=100,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        self.db.add(
            DocumentChunk(
                document_id=doc.id,
                chunk_index=0,
                page_number=1,
                category="body",
                content="Printed Slide: Transport Layer uses TCP Handshake for session setup.",
                embedding=generate_embedding("Transport Layer uses TCP Handshake"),
            )
        )
        self.db.add(
            HandwrittenPage(
                document_id=doc.id,
                page_number=2,
                original_image_path="uploads/mixed_p2.png",
                raw_transcription="Handwritten Note: SYN Flood exploits TCP Handshake on servers.",
                edited_transcription="Handwritten Note: SYN Flood exploits TCP Handshake on servers.",
                confidence_score=0.90,
            )
        )
        self.db.commit()

        res = self.client.post(f"/documents/{doc.id}/knowledge-graph", json={"skip_llm": True}, headers=self.headers_a).json()
        pages_covered = set(res["stats"]["pages_covered"])
        self.assertIn(1, pages_covered)
        self.assertIn(2, pages_covered)

    def test_22_docx_and_txt_document_types(self):
        for dtype, fname in [("DOCX", "report.docx"), ("TXT", "notes.txt")]:
            doc = self._create_printed_doc(self.user_a.id, filename=fname, doc_type=dtype)
            res = self.client.post(
                f"/documents/{doc.id}/knowledge-graph",
                json={"skip_llm": True},
                headers=self.headers_a,
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["document_type"], dtype)
            self.assertGreaterEqual(res.json()["stats"]["node_count"], 3)

    def test_23_short_or_empty_document_safe_handling(self):
        doc = Document(
            user_id=self.user_a.id,
            filename="empty.txt",
            document_type="TXT",
            file_path="uploads/empty.txt",
            extracted_text="",
            text_length=0,
            is_handwritten=False,
            processing_status="completed",
            processing_progress=100,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        res = self.client.post(
            f"/documents/{doc.id}/knowledge-graph",
            json={"skip_llm": True},
            headers=self.headers_a,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "empty")
        self.assertEqual(data["nodes"], [])
        self.assertEqual(data["edges"], [])

    def test_24_delete_endpoint_cleans_db(self):
        doc = self._create_printed_doc(self.user_a.id)
        self.client.post(f"/documents/{doc.id}/knowledge-graph", json={"skip_llm": True}, headers=self.headers_a)
        self.assertEqual(self.db.query(KnowledgeGraph).count(), 1)

        del_res = self.client.delete(f"/documents/{doc.id}/knowledge-graph", headers=self.headers_a)
        self.assertEqual(del_res.status_code, 200)
        self.assertTrue(del_res.json()["deleted"])
        self.assertEqual(self.db.query(KnowledgeGraph).count(), 0)
        self.assertEqual(self.db.query(KnowledgeGraphNode).count(), 0)
        self.assertEqual(self.db.query(KnowledgeGraphEdge).count(), 0)
        self.assertEqual(
            self.client.get(f"/documents/{doc.id}/knowledge-graph", headers=self.headers_a).status_code,
            404,
        )

    def test_25_long_document_bounded_scaling_no_n2_llm(self):
        long_pages = [
            (
                i + 1,
                f"Section {i + 1}: Protocol Module {i + 1} uses Packet Filter {i + 1} to inspect Flow Stream {i + 1}. "
                f"SYN Flood mitigates throughput when TCB Queue overflows.",
            )
            for i in range(24)
        ]
        doc = self._create_printed_doc(self.user_a.id, pages=long_pages)
        call_count = 0

        def counting_llm(prompt, system_prompt="", **kwargs):
            nonlocal call_count
            call_count += 1
            return {"relations": []}

        with patch("app.services.knowledge_graph_relationship_service.query_ollama_json", side_effect=counting_llm):
            res = self.client.post(
                f"/documents/{doc.id}/knowledge-graph",
                json={"skip_llm": False, "max_nodes": 25},
                headers=self.headers_a,
            )
        self.assertEqual(res.status_code, 200)
        self.assertLessEqual(call_count, 2)

    def test_26_cascade_safe_non_mutation_of_core_tables(self):
        doc = self._create_printed_doc(self.user_a.id)
        chunk_count_before = self.db.query(DocumentChunk).count()
        self.client.post(f"/documents/{doc.id}/knowledge-graph", json={"skip_llm": True}, headers=self.headers_a)
        self.client.delete(f"/documents/{doc.id}/knowledge-graph", headers=self.headers_a)
        self.assertEqual(self.db.query(Document).count(), 1)
        self.assertEqual(self.db.query(DocumentChunk).count(), chunk_count_before)


if __name__ == "__main__":
    unittest.main()

