import unittest
from unittest.mock import patch

from starlette.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
from app.core.security import hash_password, create_access_token
from app.models.user import User
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.handwritten_page import HandwrittenPage
from app.models.conversation import Conversation, ConversationMessage
from app.models.chat_cache import ChatQueryCache, compute_multi_doc_cache_key
from app.models.activity import ActivityLog
from app.services.embedding_services import generate_embedding
from app.services.text_processing_service import extract_relevant_excerpt
from app.services.handwriting.handwritten_source_service import sync_handwritten_chunks_and_embeddings
from app.services.llm_service import FALLBACK_ANSWER


class TestGroundedPageCitations(unittest.TestCase):
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
        Base.metadata.create_all(bind=cls.engine)

        def override_get_db():
            db = cls.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=cls.engine)

    def setUp(self):
        self.db = self.TestingSessionLocal()
        for tbl in (
            ActivityLog,
            ChatQueryCache,
            ConversationMessage,
            Conversation,
            HandwrittenPage,
            DocumentChunk,
            Document,
            User,
        ):
            self.db.query(tbl).delete()
        self.db.commit()

        self.user = User(
            id=1,
            email="citations@example.com",
            full_name="Citation Tester",
            password_hash=hash_password("Pass123!"),
            is_verified=True,
        )
        self.other_user = User(
            id=2,
            email="other@example.com",
            full_name="Other User",
            password_hash=hash_password("Pass123!"),
            is_verified=True,
        )
        self.db.add_all([self.user, self.other_user])
        self.db.commit()

        token = create_access_token({"sub": str(self.user.id)})
        self.headers = {"Authorization": f"Bearer {token}"}

    def tearDown(self):
        self.db.close()

    def _add_doc_with_pages(
        self,
        filename: str,
        pages_map: dict[int | None, str],
        user_id: int = 1,
        doc_type: str = "PDF",
        is_handwritten: bool = False,
    ) -> Document:
        full_text = "\n\n".join(text for _, text in sorted(pages_map.items(), key=lambda x: x[0] or 0))
        doc = Document(
            user_id=user_id,
            filename=filename,
            document_type=doc_type,
            file_path=f"uploads/{filename}",
            extracted_text=full_text,
            text_length=len(full_text),
            is_handwritten=is_handwritten,
            processing_status="ready",
            processing_progress=100,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        for idx, (page_num, text) in enumerate(pages_map.items()):
            emb = generate_embedding(text)
            chunk = DocumentChunk(
                document_id=doc.id,
                chunk_index=idx,
                content=text,
                embedding=emb,
                page_number=page_num,
            )
            self.db.add(chunk)
        self.db.commit()
        return doc

    # ------------------------------------------------------------------
    # 1. Smart Excerpt Selection Utility
    # ------------------------------------------------------------------
    def test_excerpt_utility_selects_relevant_tail_passage_and_cleans_ocr(self):
        long_chunk = (
            "--- Page 4 ---\n"
            "First introductory paragraph discussing general historical background and hardware evolution over decades. "
            "Hardware acceleration grew steadily throughout early university computing clusters and laboratory trials. "
            "Second paragraph covers unrelated administrative scheduling metrics for weekly department reviews. "
            "The proposed hybrid architecture combines CNN layers with Transformer self-attention blocks for multi-scale feature extraction. "
            "Finally the appendix summarizes dataset formatting."
        )
        excerpt = extract_relevant_excerpt(
            long_chunk,
            query="How does the proposed hybrid architecture combine CNN and Transformer?",
            max_chars=210,
        )
        self.assertIn("CNN", excerpt)
        self.assertIn("Transformer", excerpt)
        self.assertNotIn("--- Page 4 ---", excerpt)
        self.assertLessEqual(len(excerpt), 220)

    # ------------------------------------------------------------------
    # 2. Single Document: Grounded Answer + Page & Chunk Metadata
    # ------------------------------------------------------------------
    @patch("app.services.question_service.generate_response")
    def test_single_document_returns_structured_sources_with_page(self, mock_gen):
        mock_gen.return_value = "The model uses multi-head attention across layers [1]."
        doc = self._add_doc_with_pages(
            "research-paper.pdf",
            {
                1: "Introduction to neural document pipelines and tokenization steps.",
                4: "Our attention model uses multi-head self-attention to capture long-range dependencies across paragraphs.",
            },
        )

        res = self.client.post(
            "/documents/ask",
            json={"query": "How does multi-head attention capture dependencies?", "document_id": doc.id},
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("answer", data)
        self.assertIn("sources", data)
        self.assertGreaterEqual(len(data["sources"]), 1)

        src = data["sources"][0]
        self.assertEqual(src["document_id"], doc.id)
        self.assertEqual(src["document_name"], "research-paper.pdf")
        self.assertEqual(src["page_number"], 4)
        self.assertIn("chunk_id", src)
        self.assertIsNotNone(src["chunk_id"])
        self.assertIn("retrieval_score", src)
        self.assertIn("multi-head", src["excerpt"].lower())

        # Ensure backward compatibility keys also present
        self.assertGreaterEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["document_name"], "research-paper.pdf")

        # Verify GET /documents/{id} reconstructs navigable pages
        doc_detail = self.client.get(f"/documents/{doc.id}", headers=self.headers)
        self.assertEqual(doc_detail.status_code, 200)
        detail_json = doc_detail.json()
        self.assertEqual([p["page_number"] for p in detail_json["pages"]], [1, 4])

    # ------------------------------------------------------------------
    # 3. Multi-Page Citation Retrieval in a Single Document
    # ------------------------------------------------------------------
    @patch("app.services.question_service.generate_response")
    def test_multiple_pages_single_document_citations(self, mock_gen):
        mock_gen.return_value = (
            "The encoder combines CNN and Transformer blocks [1], and the ablation study on F1 evaluation "
            "demonstrates 94.2% accuracy [2]."
        )
        doc = self._add_doc_with_pages(
            "architecture-study.pdf",
            {
                2: "Section 2 Architecture: The proposed model combines CNN layers and Transformer blocks for visual feature extraction.",
                5: "Section 5 Experimental Evaluation: Ablation benchmark experiments on CNN Transformer evaluation achieved 94.2% F1 accuracy.",
                9: "References and acknowledgements section.",
            },
        )

        res = self.client.post(
            "/documents/ask",
            json={"query": "Describe the CNN Transformer architecture and its experimental evaluation results", "document_id": doc.id, "top_k": 5},
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        pages_cited = {s["page_number"] for s in data["sources"]}
        self.assertIn(2, pages_cited)
        self.assertIn(5, pages_cited)
        self.assertTrue(all(s["document_id"] == doc.id for s in data["sources"]))

    # ------------------------------------------------------------------
    # 4. Multi-Document Cross-Citation & Conversation Source Persistence
    # ------------------------------------------------------------------
    @patch("app.services.question_service.generate_response")
    def test_multiple_documents_attribute_correct_originating_docs_and_pages(self, mock_gen):
        mock_gen.return_value = "AES-256 encrypts storage blocks [1] whereas TLS 1.3 secures transit channels [2]."
        doc_a = self._add_doc_with_pages(
            "storage-encryption.pdf",
            {3: "Storage security mandates AES-256 block cipher encryption with rotating keys at rest."},
        )
        doc_b = self._add_doc_with_pages(
            "network-security.pdf",
            {7: "Network transit security relies on TLS 1.3 handshake protocols to authenticate peers."},
        )

        res = self.client.post(
            "/documents/ask",
            json={"query": "Compare AES-256 storage encryption and TLS 1.3 transit security protocols", "document_ids": [doc_a.id, doc_b.id]},
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        source_pairs = {(s["document_name"], s["page_number"]) for s in data["sources"]}
        self.assertIn(("storage-encryption.pdf", 3), source_pairs)
        self.assertIn(("network-security.pdf", 7), source_pairs)

        conv_id = data["conversation_id"]
        conv_res = self.client.get(f"/conversations/{conv_id}", headers=self.headers)
        self.assertEqual(conv_res.status_code, 200)
        asst_msgs = [m for m in conv_res.json()["messages"] if m["role"] == "assistant"]
        self.assertEqual(len(asst_msgs), 1)
        persisted_pairs = {(s["document_name"], s["page_number"]) for s in asst_msgs[0]["sources"]}
        self.assertEqual(source_pairs, persisted_pairs)

    # ------------------------------------------------------------------
    # 5. Unsupported Question: Refusal Without Fabricated Citations
    # ------------------------------------------------------------------
    def test_unsupported_question_refuses_without_sources_confidence_gate(self):
        doc = self._add_doc_with_pages(
            "networking-notes.pdf",
            {1: "TCP three-way handshake uses SYN, SYN-ACK, and ACK packets for connection setup."},
        )
        res = self.client.post(
            "/documents/ask",
            json={"query": "What is the secret chocolate soufflé oven temperature recipe?", "document_id": doc.id},
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["answer"], FALLBACK_ANSWER)
        self.assertEqual(data["sources"], [])
        self.assertEqual(data["results"], [])
        self.assertEqual(data["result_count"], 0)
        self.assertEqual(data["follow_up_questions"], [])

    @patch("app.services.question_service.generate_response")
    def test_unsupported_question_llm_refusal_suppresses_sources(self, mock_gen):
        mock_gen.return_value = "I couldn't find enough information in the uploaded document to answer that question."
        doc = self._add_doc_with_pages(
            "networking-notes.pdf",
            {1: "TCP connection setup covers ports and sockets in computer networking protocols."},
        )
        res = self.client.post(
            "/documents/ask",
            json={"query": "What TCP throughput benchmark was recorded in 2035?", "document_id": doc.id},
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("couldn't find enough information", data["answer"].lower())
        self.assertEqual(data["sources"], [])
        self.assertEqual(data["results"], [])
        self.assertEqual(data["result_count"], 0)

    # ------------------------------------------------------------------
    # 6. OCR Multi-Page Handwritten Notes Preserves Page Metadata
    # ------------------------------------------------------------------
    @patch("app.services.question_service.generate_response")
    def test_ocr_multipage_document_preserves_page_metadata_on_ask_and_get(self, mock_gen):
        mock_gen.return_value = "External stylesheets use a <link> element [1]."
        hw_doc = Document(
            user_id=self.user.id,
            filename="lecture-css-notes.pdf",
            document_type="HANDWRITTEN",
            file_path="uploads/handwritten/lecture-css-notes.pdf",
            is_handwritten=True,
            processing_status="ready",
            processing_progress=100,
        )
        self.db.add(hw_doc)
        self.db.commit()
        self.db.refresh(hw_doc)

        p1 = HandwrittenPage(
            document_id=hw_doc.id,
            page_number=1,
            original_image_path="orig_1.png",
            processed_image_path="proc_1.png",
            raw_transcription="HTML defines semantic structure for pages.",
            edited_transcription="HTML defines semantic structure for web pages.",
            status="completed",
        )
        p2 = HandwrittenPage(
            document_id=hw_doc.id,
            page_number=2,
            original_image_path="orig_2.png",
            processed_image_path="proc_2.png",
            raw_transcription="External CSS stylesheets use the HTML link tag inside the document head.",
            edited_transcription="External CSS stylesheets use the link tag inside the HTML head section.",
            status="completed",
        )
        self.db.add_all([p1, p2])
        self.db.commit()

        count = sync_handwritten_chunks_and_embeddings(hw_doc.id, self.db)
        self.assertGreaterEqual(count, 2)

        res = self.client.post(
            "/documents/ask",
            json={"query": "How are external CSS stylesheets linked inside HTML?", "document_id": hw_doc.id},
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreaterEqual(len(data["sources"]), 1)
        top_src = data["sources"][0]
        self.assertEqual(top_src["source_type"], "handwritten")
        self.assertEqual(top_src["document_name"], "lecture-css-notes.pdf")
        self.assertEqual(top_src["page_number"], 2)

        doc_detail = self.client.get(f"/documents/{hw_doc.id}", headers=self.headers)
        self.assertEqual(doc_detail.status_code, 200)
        self.assertEqual([p["page_number"] for p in doc_detail.json()["pages"]], [1, 2])

    # ------------------------------------------------------------------
    # 7. Real PDF Chunking Preserves Page Boundaries + Legacy Cache Normalization
    # ------------------------------------------------------------------
    def test_unpaginated_txt_keeps_page_number_none_and_legacy_cache_backfills_sources(self):
        doc = self._add_doc_with_pages(
            "plain-notes.txt",
            {None: "Plain text file describing Kubernetes pod scheduling policies cleanly."},
            doc_type="TXT",
        )
        # Seed a legacy cache entry lacking 'sources' key
        from app.services.question_service import compute_documents_combined_hash
        chash = compute_documents_combined_hash([doc.id], self.db)
        ckey = compute_multi_doc_cache_key(self.user.id, [doc.id], chash, "Explain Kubernetes pod scheduling")
        cache_entry = ChatQueryCache(
            user_id=self.user.id,
            cache_key=ckey,
            document_ids_str=str(doc.id),
            combined_content_hash=chash,
            query_text="Explain Kubernetes pod scheduling",
            response_json={
                "query": "Explain Kubernetes pod scheduling",
                "answer": "Pods are scheduled based on cluster policies [1].",
                "result_count": 1,
                "results": [
                    {
                        "document_id": doc.id,
                        "document_title": "plain notes",
                        "filename": "plain-notes.txt",
                        "document_type": "TXT",
                        "source_type": "printed",
                        "page_number": None,
                        "chunk_id": 10,
                        "citation_index": 1,
                        "content": "Plain text file describing Kubernetes pod scheduling policies cleanly.",
                        "similarity": 0.78,
                    }
                ],
                "follow_up_questions": [],
            },
        )
        self.db.add(cache_entry)
        self.db.commit()

        res = self.client.post(
            "/documents/ask",
            json={"query": "Explain Kubernetes pod scheduling", "document_id": doc.id},
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["cached"])
        self.assertIn("sources", data)
        self.assertEqual(len(data["sources"]), 1)
        self.assertEqual(data["sources"][0]["document_name"], "plain-notes.txt")
        self.assertIsNone(data["sources"][0]["page_number"])

    def test_real_pdf_processing_preserves_multipage_page_numbers(self):
        """Real 2-page PDF processed through process_document retains page 1 and page 2 metadata."""
        import tempfile
        from pathlib import Path
        from app.services.document_service import process_document

        def build_two_page_pdf(page1_text: str, page2_text: str) -> bytes:
            objects = [
                b"<< /Type /Catalog /Pages 2 0 R >>",
                b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 5 0 R /Resources << /Font << /F1 7 0 R >> >> >>",
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 6 0 R /Resources << /Font << /F1 7 0 R >> >> >>",
            ]
            for txt in (page1_text, page2_text):
                stream = f"BT /F1 12 Tf 72 720 Td ({txt}) Tj ET".encode("latin1")
                objects.append(
                    f"<< /Length {len(stream)} >>\nstream\n".encode("latin1")
                    + stream
                    + b"\nendstream"
                )
            objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

            pdf = bytearray(b"%PDF-1.4\n")
            offsets = [0]
            for idx, body in enumerate(objects, start=1):
                offsets.append(len(pdf))
                pdf.extend(f"{idx} 0 obj\n".encode("latin1"))
                pdf.extend(body)
                pdf.extend(b"\nendobj\n")
            xref_pos = len(pdf)
            pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("latin1"))
            for off in offsets[1:]:
                pdf.extend(f"{off:010d} 00000 n \n".encode("latin1"))
            pdf.extend(
                f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("latin1")
            )
            return bytes(pdf)

        p1_str = "Chapter one covers Byzantine fault tolerance quorum math."
        p2_str = "Chapter two explains Raft leader election and log replication."
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "consensus-notes.pdf"
            pdf_path.write_bytes(build_two_page_pdf(p1_str, p2_str))

            processed = process_document(pdf_path)
            self.assertEqual(processed["document_type"], "PDF")
            self.assertGreaterEqual(len(processed["chunks"]), 2)
            self.assertEqual(processed["page_numbers"], [1, 2])

            doc = Document(
                user_id=self.user.id,
                filename="consensus-notes.pdf",
                file_path=str(pdf_path),
                document_type="PDF",
                extracted_text=processed["text"],
                text_length=len(processed["text"]),
                processing_status="ready",
                processing_progress=100,
            )
            self.db.add(doc)
            self.db.flush()

            for idx, (chunk_text, emb, pnum) in enumerate(
                zip(processed["chunks"], processed["embeddings"], processed["page_numbers"])
            ):
                self.db.add(
                    DocumentChunk(
                        document_id=doc.id,
                        chunk_index=idx,
                        page_number=pnum,
                        content=chunk_text,
                        embedding=emb,
                    )
                )
            self.db.commit()

            detail = self.client.get(f"/documents/{doc.id}", headers=self.headers)
            self.assertEqual(detail.status_code, 200)
            detail_json = detail.json()
            self.assertEqual(detail_json["page_count"], 2)
            self.assertEqual([p["page_number"] for p in detail_json["pages"]], [1, 2])

            with patch(
                "app.services.question_service.generate_response",
                return_value="Raft handles leader election and log replication [1].",
            ):
                res = self.client.post(
                    "/documents/ask",
                    json={"query": "Which page explains Raft leader election?", "document_id": doc.id},
                    headers=self.headers,
                )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertGreaterEqual(len(data["sources"]), 1)
            self.assertEqual(data["sources"][0]["page_number"], 2)
            self.assertEqual(data["sources"][0]["document_name"], "consensus-notes.pdf")


if __name__ == "__main__":
    unittest.main()
