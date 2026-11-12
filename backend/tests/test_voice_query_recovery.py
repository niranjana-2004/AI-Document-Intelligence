import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.handwritten_analysis import HandwrittenConcept
from app.models.handwritten_page import HandwrittenPage
from app.models.user import User
from app.services.embedding_services import generate_embedding
from app.services.voice_query_recovery_service import (
    clear_voice_recovery_cache,
    recover_voice_query,
)
from app.services.voice_terminology_service import clear_voice_terminology_cache


_EMB_CACHE: dict[str, list[float]] = {}


def _cached_embedding(text: str) -> list[float]:
    if text not in _EMB_CACHE:
        _EMB_CACHE[text] = generate_embedding(text)
    return _EMB_CACHE[text]


class TestVoiceQueryRecovery(unittest.TestCase):
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
        clear_voice_terminology_cache()
        clear_voice_recovery_cache()
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.TestingSessionLocal()

        self.user_a = User(
            id=1,
            email="voice_p2_a@example.com",
            full_name="User Alpha",
            password_hash=hash_password("Pass123!"),
            is_verified=True,
        )
        self.user_b = User(
            id=2,
            email="voice_p2_b@example.com",
            full_name="User Beta",
            password_hash=hash_password("Pass123!"),
            is_verified=True,
        )
        self.db.add_all([self.user_a, self.user_b])
        self.db.commit()

        self.headers_a = {
            "Authorization": f"Bearer {create_access_token({'sub': str(self.user_a.id)})}"
        }
        self.headers_b = {
            "Authorization": f"Bearer {create_access_token({'sub': str(self.user_b.id)})}"
        }

        # Seed Doc 1 (Printed Computer Networks)
        net_text = (
            "# TCP Attacks\n\n"
            "## 1. SYN Flood\n"
            "A SYN flood is a denial-of-service (DoS) attack exploiting the TCP three-way handshake "
            "(SYN, SYN-ACK, ACK). The server allocates a Transmission Control Block (TCB) in its "
            "backlog queue for each spoofed SYN packet. SYN cookies mitigate SYN flood exhaustion.\n\n"
            "## 2. TCP RST Attack\n"
            "In a TCP RST attack, an attacker forges reset packets. Stricter validation under "
            "RFC 5961 prevents spoofed RST injection. Ingress filtering (BCP 38) blocks DDoS floods.\n"
        )
        self.doc_net = self._create_doc(
            doc_id=1,
            user_id=1,
            filename="tcp_attacks_printed.pdf",
            text=net_text,
            is_handwritten=False,
        )

        # Seed Doc 2 (Handwritten Web Development / CSS notes)
        css_text = (
            "# Introduction to CSS\n"
            "CSS stands for Cascading Style Sheets. CSS describes the styling and layout of HTML documents. "
            "Separation of concerns keeps HTML structure separate from CSS styles."
        )
        self.doc_css = self._create_doc(
            doc_id=2,
            user_id=1,
            filename="css_handwritten_notes.webp",
            text=css_text,
            is_handwritten=True,
            edited_pages=[css_text],
            concepts=["Cascading Style Sheets (CSS)", "HTML", "CSS"],
        )

        # Seed Doc 3 (Physics printed doc - arbitrary domain non-TCP)
        phys_text = (
            "# Electromagnetic Induction & Quantum Optics\n"
            "Faraday's law relates induced electromotive force (EMF) to magnetic flux change. "
            "The Schrodinger equation describes quantum wave evolution. A light-emitting diode (LED) "
            "emits photons via electroluminescence."
        )
        self.doc_phys = self._create_doc(
            doc_id=3,
            user_id=1,
            filename="physics_optics.pdf",
            text=phys_text,
            is_handwritten=False,
        )

        # Seed Doc 4 (Tenant Beta secret doc)
        beta_text = (
            "# Project XYZQ Architecture\n"
            "XYZQ is a proprietary satellite telemetry protocol developed by Beta Corp."
        )
        self.doc_beta = self._create_doc(
            doc_id=4,
            user_id=2,
            filename="beta_secret.pdf",
            text=beta_text,
            is_handwritten=False,
        )

    def tearDown(self):
        self.db.close()

    def _create_doc(
        self,
        doc_id: int,
        user_id: int,
        filename: str,
        text: str,
        is_handwritten: bool = False,
        raw_pages: list[str] | None = None,
        edited_pages: list[str] | None = None,
        concepts: list[str] | None = None,
    ) -> Document:
        doc = Document(
            id=doc_id,
            user_id=user_id,
            filename=filename,
            document_type="HANDWRITTEN" if is_handwritten else "PDF",
            file_path=filename,
            extracted_text=text,
            text_length=len(text or ""),
            is_handwritten=is_handwritten,
            processing_status="completed",
            processing_progress=100,
        )
        self.db.add(doc)
        self.db.flush()

        chunks_src = edited_pages or raw_pages or ([text] if text and text.strip() else [])
        for idx, c_txt in enumerate(chunks_src, start=1):
            if not c_txt or not c_txt.strip():
                continue
            emb = _cached_embedding(c_txt)
            self.db.add(
                DocumentChunk(
                    document_id=doc.id,
                    chunk_index=idx - 1,
                    category="handwritten" if is_handwritten else "general",
                    content=c_txt,
                    embedding=emb,
                    page_number=idx,
                )
            )

        if is_handwritten:
            import hashlib
            full_src = "\n\n".join(
                f"--- Page {pno} ---\n{p}" for pno, p in enumerate(chunks_src, start=1) if p
            )
            h_val = hashlib.sha256(full_src.encode("utf-8")).hexdigest() if full_src else ""
            pages_count = max(len(raw_pages or []), len(edited_pages or []), len(chunks_src))
            for p_idx in range(pages_count):
                r_txt = raw_pages[p_idx] if raw_pages and p_idx < len(raw_pages) else (chunks_src[p_idx] if p_idx < len(chunks_src) else "")
                e_txt = edited_pages[p_idx] if edited_pages and p_idx < len(edited_pages) else ""
                self.db.add(
                    HandwrittenPage(
                        document_id=doc.id,
                        page_number=p_idx + 1,
                        original_image_path=f"p{p_idx + 1}.png",
                        raw_transcription=r_txt,
                        edited_transcription=e_txt,
                        confidence_score=0.92,
                    )
                )
            for cname in (concepts or []):
                self.db.add(
                    HandwrittenConcept(
                        document_id=doc.id,
                        user_id=user_id,
                        name=cname,
                        definition=f"Definition of {cname}",
                        page_number=1,
                        transcription_hash=h_val,
                    )
                )

        self.db.commit()
        return doc

    # 1. Exact clean transcript
    def test_01_exact_clean_transcript_remains_unchanged(self):
        for clean_q in ["What is a SYN flood?", "What is TCP?", "What are SYN cookies?"]:
            res = recover_voice_query(clean_q, db=self.db, user_id=1, document_ids=[1])
            self.assertEqual(res.decision, "UNCHANGED")
            self.assertFalse(res.recovery_applied)
            self.assertEqual(res.raw_transcript, clean_q)
            self.assertEqual(res.recovered_transcript, clean_q)

    # 2. Acronym spacing
    def test_02_spaced_acronyms_recovered_across_domains(self):
        r_tcp = recover_voice_query("What is T C P?", db=self.db, user_id=1, document_ids=[1])
        self.assertEqual(r_tcp.decision, "RECOVERED")
        self.assertEqual(r_tcp.recovered_transcript, "What is TCP?")

        r_syn = recover_voice_query("What is a S Y N flood?", db=self.db, user_id=1, document_ids=[1])
        self.assertEqual(r_syn.decision, "RECOVERED")
        self.assertEqual(r_syn.recovered_transcript, "What is a SYN flood?")

        r_emf = recover_voice_query("Explain E M F in physics", db=self.db, user_id=1, document_ids=[3])
        self.assertEqual(r_emf.decision, "RECOVERED")
        self.assertEqual(r_emf.recovered_transcript, "Explain EMF in physics")

    # 3. Hyphenated acronym (real Chrome Phase 1 artifact 'S-Y-N-Flood')
    def test_03_hyphenated_acronym_recovered(self):
        res = recover_voice_query("What is S-Y-N-Flood?", db=self.db, user_id=1, document_ids=[1])
        self.assertEqual(res.decision, "RECOVERED")
        self.assertTrue(res.recovery_applied)
        self.assertEqual(res.raw_transcript, "What is S-Y-N-Flood?")
        self.assertEqual(res.recovered_transcript, "What is SYN flood?")

    # 4. Phonetically distorted acronym ('swion' -> 'SYN', 'rest' with colocation -> 'RST')
    def test_04_phonetically_distorted_acronym_recovered(self):
        res_swion = recover_voice_query("What is a swion flood?", db=self.db, user_id=1, document_ids=[1])
        self.assertEqual(res_swion.decision, "RECOVERED")
        self.assertTrue(res_swion.recovery_applied)
        self.assertEqual(res_swion.raw_transcript, "What is a swion flood?")
        self.assertEqual(res_swion.recovered_transcript, "What is a SYN flood?")

        res_rst = recover_voice_query("What is a TCP rest attack?", db=self.db, user_id=1, document_ids=[1])
        self.assertEqual(res_rst.decision, "RECOVERED")
        self.assertEqual(res_rst.recovered_transcript, "What is a TCP RST attack?")

    # 5. Technical term + spoken standard identifier & punctuation normalization
    def test_05_technical_term_and_spoken_number_punctuation_recovery(self):
        res_rfc = recover_voice_query(
            "What is R F C five nine six one question mark",
            db=self.db,
            user_id=1,
            document_ids=[1],
        )
        self.assertEqual(res_rfc.decision, "RECOVERED")
        self.assertEqual(res_rfc.recovered_transcript, "What is RFC 5961?")

        res_bcp = recover_voice_query("Explain B C P thirty eight", db=self.db, user_id=1, document_ids=[1])
        self.assertEqual(res_bcp.decision, "RECOVERED")
        self.assertEqual(res_bcp.recovered_transcript, "Explain BCP 38")

        res_schrod = recover_voice_query("What is the Shrodinger equation?", db=self.db, user_id=1, document_ids=[3])
        self.assertEqual(res_schrod.decision, "RECOVERED")
        self.assertEqual(res_schrod.recovered_transcript, "What is the Schrodinger equation?")

    # 6. Ordinary word that resembles acronym is NOT mutated in ordinary prose
    def test_06_ordinary_word_resembling_acronym_protected_in_normal_prose(self):
        res_prose = recover_voice_query(
            "Why do people commit sin and seek forgiveness",
            db=self.db,
            user_id=1,
            document_ids=[1],
        )
        self.assertEqual(res_prose.decision, "UNCHANGED")
        self.assertFalse(res_prose.recovery_applied)
        self.assertEqual(res_prose.recovered_transcript, "Why do people commit sin and seek forgiveness")

        res_rest = recover_voice_query(
            "I should get some rest before tomorrow",
            db=self.db,
            user_id=1,
            document_ids=[1],
        )
        self.assertEqual(res_rest.decision, "UNCHANGED")
        self.assertFalse(res_rest.recovery_applied)

    # 7. Ambiguous term proposes suggestion WITHOUT silently rewriting query
    def test_07_ambiguous_term_suggests_without_auto_rewrite(self):
        res = recover_voice_query("What is sin?", db=self.db, user_id=1, document_ids=[1])
        self.assertIn(res.decision, ("SUGGESTED", "AMBIGUOUS"))
        self.assertFalse(res.recovery_applied)
        self.assertEqual(res.recovered_transcript, "What is sin?")
        self.assertTrue(any(s.suggested_span == "SYN" for s in res.suggestions))

    # 8. No selected document -> zero rewrite
    def test_08_no_selected_document_returns_unchanged(self):
        res = recover_voice_query("What is a swion flood?", db=self.db, user_id=1, document_ids=[])
        self.assertEqual(res.decision, "UNCHANGED")
        self.assertFalse(res.recovery_applied)
        self.assertEqual(res.recovered_transcript, "What is a swion flood?")
        self.assertEqual(res.document_scope_count, 0)

    # 9. Single printed document (Physics)
    def test_09_single_printed_document_physics_recovery(self):
        res = recover_voice_query("How does an L E D work?", db=self.db, user_id=1, document_ids=[3])
        self.assertEqual(res.decision, "RECOVERED")
        self.assertEqual(res.recovered_transcript, "How does an LED work?")

    # 10. Single handwritten document (CSS notes)
    def test_10_single_handwritten_document_css_recovery(self):
        res = recover_voice_query("What is C S S used for?", db=self.db, user_id=1, document_ids=[2])
        self.assertEqual(res.decision, "RECOVERED")
        self.assertEqual(res.recovered_transcript, "What is CSS used for?")

    # 11. Multiple selected documents (Printed Net + Handwritten CSS + Printed Physics)
    def test_11_multi_document_scope_combines_selected_terminology(self):
        res = recover_voice_query(
            "Compare S Y N flood and C S S and L E D",
            db=self.db,
            user_id=1,
            document_ids=[1, 2, 3],
        )
        self.assertEqual(res.decision, "RECOVERED")
        self.assertEqual(res.recovered_transcript, "Compare SYN flood and CSS and LED")
        self.assertEqual(res.document_scope_count, 3)

    # 12. Unselected document terminology strictly excluded
    def test_12_unselected_document_terminology_strictly_excluded(self):
        # Select ONLY CSS Doc (id=2), NOT Networking Doc (id=1)
        res = recover_voice_query("What is a swion flood?", db=self.db, user_id=1, document_ids=[2])
        self.assertEqual(res.decision, "UNCHANGED")
        self.assertFalse(res.recovery_applied)
        self.assertEqual(res.recovered_transcript, "What is a swion flood?")

    # 13. Manual transcript edit protection
    def test_13_manual_transcript_edit_is_strictly_protected(self):
        res = self.client.post(
            "/voice/recover-query",
            json={
                "raw_transcript": "What is a swion flood?",
                "document_ids": [1],
                "manual_override": True,
                "manually_edited_transcript": "What is my exact custom edit?",
            },
            headers=self.headers_a,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["decision"], "MANUAL")
        self.assertFalse(data["recovery_applied"])
        self.assertEqual(data["recovered_transcript"], "What is my exact custom edit?")

    # 14. Low-confidence abstention
    def test_14_low_confidence_abstention_keeps_raw_transcript(self):
        res = recover_voice_query("What is blargleflon?", db=self.db, user_id=1, document_ids=[1])
        self.assertEqual(res.decision, "UNCHANGED")
        self.assertFalse(res.recovery_applied)
        self.assertEqual(res.suggestions, [])
        self.assertEqual(res.recovered_transcript, "What is blargleflon?")

    # 15. Retrieval fallback to raw query when recovered fails
    def test_15_ask_ai_retrieval_fallback_retries_raw_query_on_insufficient_recovered(self):
        # Case A: Recovered misses, raw hits strongly (CSS doc=2)
        with patch(
            "app.services.question_service.generate_response",
            return_value="Cascading Style Sheets define HTML presentation [1].",
        ) as mock_llm:
            resp = self.client.post(
                "/documents/ask",
                json={
                    "query": "Explain quantum wavefunctions unrelatedxyz",
                    "raw_query": "What is CSS in HTML?",
                    "query_source": "voice",
                    "document_ids": [2],
                },
                headers=self.headers_a,
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["retrieval_fallback_used"])
        self.assertGreater(body["result_count"], 0)
        self.assertTrue(mock_llm.called)
        self.assertEqual(mock_llm.call_args.kwargs["query"], "What is CSS in HTML?")

        # Case B: Both miss -> grounded refusal preserved cleanly (no hallucination)
        resp_miss = self.client.post(
            "/documents/ask",
            json={
                "query": "Explain Mars Rover navigation systems",
                "raw_query": "Explain Mars Rover wheels",
                "query_source": "voice",
                "document_ids": [2],
            },
            headers=self.headers_a,
        )
        self.assertEqual(resp_miss.status_code, 200)
        self.assertEqual(resp_miss.json()["result_count"], 0)
        self.assertEqual(resp_miss.json()["sources"], [])

    # 16. Cache reuse
    def test_16_terminology_cache_reused_on_repeat_request(self):
        r1 = recover_voice_query("What is a swion flood?", db=self.db, user_id=1, document_ids=[1])
        self.assertFalse(r1.cache_hit)
        r2 = recover_voice_query("What is S Y N?", db=self.db, user_id=1, document_ids=[1])
        self.assertTrue(r2.cache_hit)
        self.assertEqual(r2.recovered_transcript, "What is SYN?")

    # 17. Cache invalidation after document or handwritten version change
    def test_17_cache_invalidates_after_document_content_edit(self):
        r1 = recover_voice_query("What is Q R S T?", db=self.db, user_id=1, document_ids=[2])
        self.assertEqual(r1.decision, "UNCHANGED")
        self.assertFalse(r1.cache_hit)

        r2 = recover_voice_query("What is Q R S T?", db=self.db, user_id=1, document_ids=[2])
        self.assertTrue(r2.cache_hit)

        # Edit handwritten transcription page -> hash changes -> cache invalidates -> QRST now recovers!
        page = self.db.query(HandwrittenPage).filter(HandwrittenPage.document_id == 2).first()
        page.edited_transcription = page.edited_transcription + "\nAlso covers QRST styling rules."
        self.db.commit()

        r3 = recover_voice_query("What is Q R S T?", db=self.db, user_id=1, document_ids=[2])
        self.assertFalse(r3.cache_hit)
        self.assertEqual(r3.decision, "RECOVERED")
        self.assertEqual(r3.recovered_transcript, "What is QRST?")

    # 18. Tenant isolation & JWT auth
    def test_18_tenant_isolation_and_jwt_protection(self):
        # Unauthenticated -> 401
        r_unauth = self.client.post(
            "/voice/recover-query",
            json={"raw_transcript": "What is a swion flood?", "document_ids": [1]},
        )
        self.assertEqual(r_unauth.status_code, 401)

        # User A querying User B's document (id=4) -> 404
        r_cross = self.client.post(
            "/voice/recover-query",
            json={"raw_transcript": "What is X Y Z Q?", "document_ids": [4]},
            headers=self.headers_a,
        )
        self.assertEqual(r_cross.status_code, 404)

        # User A in 'All Documents' mode (document_ids=None) never sees User B's 'XYZQ'
        r_all_a = self.client.post(
            "/voice/recover-query",
            json={"raw_transcript": "What is X Y Z Q?"},
            headers=self.headers_a,
        )
        self.assertEqual(r_all_a.status_code, 200)
        self.assertEqual(r_all_a.json()["decision"], "UNCHANGED")

        # User B querying User B's doc -> recovers 'XYZQ'
        r_b = self.client.post(
            "/voice/recover-query",
            json={"raw_transcript": "What is X Y Z Q?", "document_ids": [4]},
            headers=self.headers_b,
        )
        self.assertEqual(r_b.status_code, 200)
        self.assertEqual(r_b.json()["recovered_transcript"], "What is XYZQ?")

    # 19. Empty query safe handling
    def test_19_empty_query_handled_safely(self):
        res = self.client.post(
            "/voice/recover-query",
            json={"raw_transcript": "   ", "document_ids": [1]},
            headers=self.headers_a,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["decision"], "UNCHANGED")
        self.assertFalse(data["recovery_applied"])

    # 20. Corrupted / empty document terminology context
    def test_20_empty_or_corrupted_document_context_safe_abstention(self):
        empty_doc = self._create_doc(
            doc_id=5,
            user_id=1,
            filename="corrupted_empty.pdf",
            text="   \n\x00   ",
            is_handwritten=False,
        )
        res = recover_voice_query(
            "What is a swion flood?",
            db=self.db,
            user_id=1,
            document_ids=[empty_doc.id],
        )
        self.assertEqual(res.decision, "UNCHANGED")
        self.assertFalse(res.recovery_applied)
        self.assertEqual(res.recovered_transcript, "What is a swion flood?")

    # 21. Multi-modal retrieval end-to-end with recovered query preserves citations & prompt safety
    def test_21_recovered_voice_query_improves_grounded_ask_ai_without_fabrication(self):
        with patch(
            "app.services.question_service.generate_response",
            return_value="A SYN flood exploits the TCP three-way handshake [1].",
        ):
            r_ask = self.client.post(
                "/documents/ask",
                json={
                    "query": "What is a SYN flood?",
                    "raw_query": "What is a swion flood?",
                    "query_source": "voice",
                    "document_ids": [1, 2],
                },
                headers=self.headers_a,
            )
        self.assertEqual(r_ask.status_code, 200)
        payload = r_ask.json()
        self.assertGreater(payload["result_count"], 0)
        self.assertFalse(payload["retrieval_fallback_used"])
        self.assertTrue(len(payload["sources"]) >= 1)
        self.assertEqual(payload["sources"][0]["document_id"], 1)


if __name__ == "__main__":
    unittest.main()
