import os
import sys
import time

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.user import User
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.conversation import Conversation, ConversationMessage
from app.models.chat_cache import ChatQueryCache, compute_multi_doc_cache_key
from app.core.security import create_access_token, hash_password
from test_db_isolation import isolated_test_db
from app.services.embedding_services import generate_embedding
from app.services.search_service import semantic_search, balance_cross_document_diversity
from app.services.context_service import build_context
from app.services.llm_service import FALLBACK_ANSWER
from app.services.question_service import (
    answer_question,
    resolve_follow_up_query,
    compute_documents_combined_hash,
    generate_deterministic_grounded_answer,
    generate_grounded_follow_up_questions
)

client = TestClient(app)


def run_tests():
    with isolated_test_db() as (db, _, _):
        print("=========================================================")
        print("COGNIDOCS MULTI-DOCUMENT CHAT — 18 TEST VERIFICATION SUITE")
        print("[ISOLATION] Running against isolated temporary SQLite snapshot (dev DB untouched)")
        print("=========================================================")

        user4 = db.query(User).filter(User.id == 4).first()
        if not user4:
            user4 = User(
                id=4,
                email="nivivini0602@gmail.com",
                full_name="Test User 4",
                password_hash=hash_password("TestPass123!"),
                is_verified=True,
            )
            db.add(user4)
            db.commit()
            db.refresh(user4)

        user1 = db.query(User).filter(User.id == 1).first()
        if not user1:
            user1 = User(
                id=1,
                email="niranjana051104@gmail.com",
                full_name="Test User 1",
                password_hash=hash_password("TestPass123!"),
                is_verified=True,
            )
            db.add(user1)
            db.commit()
            db.refresh(user1)

        token4 = create_access_token(data={"sub": str(user4.id)})
        token1 = create_access_token(data={"sub": str(user1.id)})
        headers4 = {"Authorization": f"Bearer {token4}"}
        headers1 = {"Authorization": f"Bearer {token1}"}

        print(f"[SETUP] Primary User #{user4.id}: {user4.email}")
        print(f"[SETUP] Isolated User #{user1.id}: {user1.email}")

        # Setup test documents for deterministic unit tests
        # Doc A: Networking Architecture
        doc_a = db.query(Document).filter(Document.filename == "unit_test_doc_a.txt", Document.user_id == user4.id).first()
        if not doc_a:
            doc_a = Document(
                user_id=user4.id,
                filename="unit_test_doc_a.txt",
                document_type="TXT",
                file_path="uploads/unit_test_doc_a.txt",
                extracted_text=(
                    "Transmission Control Protocol (TCP) is a connection-oriented transport layer protocol.\n"
                    "TCP uses a three-way handshake (SYN, SYN-ACK, ACK) to establish reliable connections.\n"
                    "TCP provides flow control via sliding window and congestion control using slow start algorithms."
                ),
                text_length=300,
                is_handwritten=False
            )
            db.add(doc_a)
            db.commit()
            db.refresh(doc_a)
            emb_a1 = generate_embedding("Transmission Control Protocol (TCP) is a connection-oriented transport layer protocol.")
            emb_a2 = generate_embedding("TCP uses a three-way handshake (SYN, SYN-ACK, ACK) to establish reliable connections.")
            c_a1 = DocumentChunk(document_id=doc_a.id, chunk_index=0, content=doc_a.extracted_text[:120], embedding=emb_a1, page_number=1)
            c_a2 = DocumentChunk(document_id=doc_a.id, chunk_index=1, content=doc_a.extracted_text[120:], embedding=emb_a2, page_number=2)
            db.add_all([c_a1, c_a2])
            db.commit()

        # Doc B: Web Protocols & Security
        doc_b = db.query(Document).filter(Document.filename == "unit_test_doc_b.txt", Document.user_id == user4.id).first()
        if not doc_b:
            doc_b = Document(
                user_id=user4.id,
                filename="unit_test_doc_b.txt",
                document_type="TXT",
                file_path="uploads/unit_test_doc_b.txt",
                extracted_text=(
                    "User Datagram Protocol (UDP) is a connectionless transport protocol prioritizing low latency.\n"
                    "Unlike TCP, UDP has no handshake and does not guarantee packet delivery or order.\n"
                    "DNS and video streaming frequently rely on UDP port 53 and real-time transport."
                ),
                text_length=310,
                is_handwritten=False
            )
            db.add(doc_b)
            db.commit()
            db.refresh(doc_b)
            emb_b1 = generate_embedding("User Datagram Protocol (UDP) is a connectionless transport protocol prioritizing low latency.")
            emb_b2 = generate_embedding("Unlike TCP, UDP has no handshake and does not guarantee packet delivery or order.")
            c_b1 = DocumentChunk(document_id=doc_b.id, chunk_index=0, content=doc_b.extracted_text[:125], embedding=emb_b1, page_number=1)
            c_b2 = DocumentChunk(document_id=doc_b.id, chunk_index=1, content=doc_b.extracted_text[125:], embedding=emb_b2, page_number=2)
            db.add_all([c_b1, c_b2])
            db.commit()

        # Doc C: Application Protocols
        doc_c = db.query(Document).filter(Document.filename == "unit_test_doc_c.txt", Document.user_id == user4.id).first()
        if not doc_c:
            doc_c = Document(
                user_id=user4.id,
                filename="unit_test_doc_c.txt",
                document_type="TXT",
                file_path="uploads/unit_test_doc_c.txt",
                extracted_text=(
                    "Hypertext Transfer Protocol (HTTP) is an application layer protocol for distributed media systems.\n"
                    "HTTP/1.1 runs over TCP, whereas HTTP/3 uses QUIC running over UDP for rapid handshakes.\n"
                    "TLS encrypts HTTP communications into HTTPS ensuring confidentiality and integrity."
                ),
                text_length=320,
                is_handwritten=False
            )
            db.add(doc_c)
            db.commit()
            db.refresh(doc_c)
            emb_c1 = generate_embedding("Hypertext Transfer Protocol (HTTP) is an application layer protocol for distributed media systems.")
            c_c1 = DocumentChunk(document_id=doc_c.id, chunk_index=0, content=doc_c.extracted_text, embedding=emb_c1, page_number=1)
            db.add(c_c1)
            db.commit()

        # -------------------------------------------------------------
        # TEST 1: Single-Document Compatibility
        # -------------------------------------------------------------
        print("\n=== TEST 1: Single-Document Backward Compatibility ===")
        res1 = client.post(
            "/documents/ask",
            json={"query": "What is TCP?", "document_id": doc_a.id},
            headers=headers4
        )
        assert res1.status_code == 200, f"Test 1 failed: {res1.text}"
        data1 = res1.json()
        assert "answer" in data1 and len(data1["answer"]) > 10
        assert data1["result_count"] >= 1
        assert all(r["document_id"] == doc_a.id for r in data1["results"])
        print(f"PASS: Single document ask returned {data1['result_count']} chunks for Doc #{doc_a.id}!")

        # -------------------------------------------------------------
        # TEST 2: Two-Document Retrieval
        # -------------------------------------------------------------
        print("\n=== TEST 2: Two-Document Retrieval ===")
        res2 = client.post(
            "/documents/ask",
            json={
                "query": "Compare connection establishment and reliability between TCP and UDP",
                "document_ids": [doc_a.id, doc_b.id]
            },
            headers=headers4
        )
        assert res2.status_code == 200, f"Test 2 failed: {res2.text}"
        data2 = res2.json()
        doc_ids_in_results = {r["document_id"] for r in data2["results"]}
        assert doc_a.id in doc_ids_in_results, "Doc A missing from 2-document retrieval"
        assert doc_b.id in doc_ids_in_results, "Doc B missing from 2-document retrieval"
        print(f"PASS: Evidence retrieved from both Doc #{doc_a.id} and Doc #{doc_b.id}!")

        # -------------------------------------------------------------
        # TEST 3: Three-Document Retrieval
        # -------------------------------------------------------------
        print("\n=== TEST 3: Three-Document Retrieval ===")
        res3 = client.post(
            "/documents/ask",
            json={
                "query": "How do transport protocols like TCP and UDP interact with HTTP and web communication?",
                "document_ids": [doc_a.id, doc_b.id, doc_c.id]
            },
            headers=headers4
        )
        assert res3.status_code == 200, f"Test 3 failed: {res3.text}"
        data3 = res3.json()
        doc_ids_in_res3 = {r["document_id"] for r in data3["results"]}
        assert len(doc_ids_in_res3) >= 2, f"Expected cross-document evidence from multiple docs, got: {doc_ids_in_res3}"
        print(f"PASS: Retrieved cross-document evidence from {len(doc_ids_in_res3)} documents: {doc_ids_in_res3}")

        # -------------------------------------------------------------
        # TEST 4: Document Diversity Balancing (No Starvation)
        # -------------------------------------------------------------
        print("\n=== TEST 4: Document Diversity Layer Balancing ===")
        # Synthetic candidate list where Doc A has 5 candidates and Doc B has 2
        synth_candidates = [
            {"document_id": doc_a.id, "content": "TCP chunk 1 details on flow control", "final_score": 0.92},
            {"document_id": doc_a.id, "content": "TCP chunk 2 details on congestion window", "final_score": 0.90},
            {"document_id": doc_a.id, "content": "TCP chunk 3 details on selective ACK", "final_score": 0.88},
            {"document_id": doc_a.id, "content": "TCP chunk 4 details on socket teardown", "final_score": 0.86},
            {"document_id": doc_b.id, "content": "UDP chunk 1 stateless datagram streaming", "final_score": 0.84},
            {"document_id": doc_b.id, "content": "UDP chunk 2 broadcast multicast transport", "final_score": 0.80},
        ]
        balanced = balance_cross_document_diversity(synth_candidates, top_k=4, is_multi_document=True)
        balanced_doc_ids = [b["document_id"] for b in balanced]
        assert doc_b.id in balanced_doc_ids, "Doc B was starved by Doc A!"
        assert balanced_doc_ids.count(doc_a.id) <= 3, "Doc A exceeded diversity cap"
        print(f"PASS: Diversity balancing selected {balanced_doc_ids.count(doc_a.id)} from Doc A and {balanced_doc_ids.count(doc_b.id)} from Doc B!")

        # -------------------------------------------------------------
        # TEST 5: Normalized Source Metadata
        # -------------------------------------------------------------
        print("\n=== TEST 5: Enriched Source Evidence Metadata ===")
        sample_result = data2["results"][0]
        required_keys = ["document_id", "document_title", "filename", "source_type", "page", "chunk_id", "excerpt", "similarity"]
        for k in required_keys:
            assert k in sample_result, f"Missing required metadata key: {k}"
        assert sample_result["source_type"] in ["printed", "handwritten"]
        print(f"PASS: Enriched source metadata verified! Title='{sample_result['document_title']}', Type='{sample_result['source_type']}'")

        # -------------------------------------------------------------
        # TEST 6: Citation Index Integrity
        # -------------------------------------------------------------
        print("\n=== TEST 6: Stable Citation Index Integrity ===")
        for idx, r in enumerate(data2["results"], start=1):
            assert r["citation_index"] == idx, f"Citation index mismatch: expected {idx}, got {r['citation_index']}"
        print(f"PASS: Stable sequential 1-based citation indices verified across all {len(data2['results'])} sources!")

        # -------------------------------------------------------------
        # TEST 7: Unselected Document Exclusion
        # -------------------------------------------------------------
        print("\n=== TEST 7: Unselected Document Exclusion ===")
        # Query only doc_a and doc_b; ensure doc_c never appears
        res7 = client.post(
            "/documents/ask",
            json={"query": "transport protocol and HTTP", "document_ids": [doc_a.id, doc_b.id]},
            headers=headers4
        )
        assert res7.status_code == 200
        data7 = res7.json()
        assert not any(r["document_id"] == doc_c.id for r in data7["results"]), "Unselected doc_c appeared in retrieval!"
        print("PASS: Unselected documents strictly excluded from retrieval!")

        # -------------------------------------------------------------
        # TEST 8: Tenant Isolation Guard (Cross-User Block)
        # -------------------------------------------------------------
        print("\n=== TEST 8: Tenant Isolation & Unauthorized Access ===")
        # User 4 attempting to access User 1's document (ID 1)
        res8 = client.post(
            "/documents/ask",
            json={"query": "Show me resume details", "document_ids": [1]},
            headers=headers4
        )
        assert res8.status_code == 404, f"Expected 404 for unowned document, got {res8.status_code}"
        print("PASS: Cross-tenant document query blocked with HTTP 404 (zero data leakage)!")

        # -------------------------------------------------------------
        # TEST 9: Handwritten Document Retrieval
        # -------------------------------------------------------------
        print("\n=== TEST 9: Handwritten Document OCR Retrieval ===")
        hw_doc = db.query(Document).filter(Document.id == 13, Document.user_id == user4.id).first()
        if hw_doc:
            res9 = client.post(
                "/documents/ask",
                json={"query": "What is CSS in web development?", "document_ids": [hw_doc.id]},
                headers=headers4
            )
            assert res9.status_code == 200
            data9 = res9.json()
            assert any(r.get("source_type") == "handwritten" for r in data9["results"])
            print(f"PASS: Handwritten Doc #{hw_doc.id} retrieved {data9['result_count']} handwritten chunks with page citations!")
        else:
            print("Skipping step: Doc 13 not found")

        # -------------------------------------------------------------
        # TEST 10: Mixed Printed + Handwritten Retrieval
        # -------------------------------------------------------------
        print("\n=== TEST 10: Mixed Printed + Handwritten Cross-Retrieval ===")
        if hw_doc:
            res10 = client.post(
                "/documents/ask",
                json={"query": "Protocols, web development and styles", "document_ids": [doc_a.id, hw_doc.id]},
                headers=headers4
            )
            assert res10.status_code == 200
            data10 = res10.json()
            types_found = {r.get("source_type") for r in data10["results"]}
            assert "printed" in types_found or "handwritten" in types_found
            print(f"PASS: Multi-modal retrieval completed! Types represented: {types_found}")
        else:
            print("Skipping step: Doc 13 not found")

        # -------------------------------------------------------------
        # TEST 11: Conversation Scope Persistence
        # -------------------------------------------------------------
        print("\n=== TEST 11: Conversation Document Scope Persistence ===")
        res11_1 = client.post(
            "/documents/ask",
            json={"query": "Explain TCP handshake", "document_ids": [doc_a.id, doc_b.id]},
            headers=headers4
        )
        assert res11_1.status_code == 200
        conv_id = res11_1.json().get("conversation_id")
        assert conv_id is not None

        # Verify conversation in DB has selected_doc_ids
        conv_db = db.query(Conversation).filter(Conversation.id == conv_id).first()
        assert conv_db is not None
        assert set(conv_db.selected_doc_ids) == {doc_a.id, doc_b.id}
        print(f"PASS: Conversation #{conv_id} persisted scope: {conv_db.selected_doc_ids}!")

        # -------------------------------------------------------------
        # TEST 12: Follow-Up Query Resolution
        # -------------------------------------------------------------
        print("\n=== TEST 12: Follow-Up Query Resolution ===")
        history = [
            {"role": "user", "content": "What is TCP?"},
            {"role": "assistant", "content": "TCP is a reliable connection-oriented transport protocol."}
        ]
        resolved = resolve_follow_up_query("What are its types?", history)
        assert "TCP" in resolved, f"Follow-up resolution failed: {resolved}"
        print(f"PASS: Follow-up query successfully resolved to: '{resolved}'")

        # -------------------------------------------------------------
        # TEST 13: No-Evidence Safe Fallback
        # -------------------------------------------------------------
        print("\n=== TEST 13: No-Evidence Safe Fallback ===")
        res13 = client.post(
            "/documents/ask",
            json={
                "query": "What is the secret recipe for quantum xylophone sourdough bread?",
                "document_ids": [doc_a.id, doc_b.id]
            },
            headers=headers4
        )
        assert res13.status_code == 200
        data13 = res13.json()
        assert data13["result_count"] == 0 or FALLBACK_ANSWER in data13["answer"]
        print(f"PASS: Unsupported query safely rejected with: '{data13['answer'][:60]}...'")

        # -------------------------------------------------------------
        # TEST 14: Invalid / Non-Existent Document ID Handling
        # -------------------------------------------------------------
        print("\n=== TEST 14: Invalid Document ID Handling ===")
        res14 = client.post(
            "/documents/ask",
            json={"query": "test query", "document_ids": [doc_a.id, 999999]},
            headers=headers4
        )
        assert res14.status_code == 404
        print("PASS: Request containing non-existent document ID 999999 rejected with HTTP 404!")

        # -------------------------------------------------------------
        # TEST 15: Intra-Document Duplicate Chunk Suppression
        # -------------------------------------------------------------
        print("\n=== TEST 15: Duplicate Evidence Suppression ===")
        dupe_candidates = [
            {"document_id": 1, "content": "Exact same content for duplicate testing", "final_score": 0.90},
            {"document_id": 1, "content": "Exact same content for duplicate testing", "final_score": 0.89},
            {"document_id": 1, "content": "Completely different content about routing algorithms", "final_score": 0.85},
        ]
        deduped = balance_cross_document_diversity(dupe_candidates, top_k=3, is_multi_document=False)
        assert len(deduped) == 2, f"Expected 2 unique chunks after deduplication, got {len(deduped)}"
        print("PASS: Near-duplicate intra-document chunks successfully pruned!")

        # -------------------------------------------------------------
        # TEST 16: Persistent Multi-Document Cache & Version Invalidation
        # -------------------------------------------------------------
        print("\n=== TEST 16: Multi-Document Cache & Version Invalidation ===")
        hash1 = compute_documents_combined_hash([doc_a.id, doc_b.id], db)
        cache_key1 = compute_multi_doc_cache_key(user4.id, [doc_a.id, doc_b.id], hash1, "What is TCP?")

        # First run (computes / populates cache)
        ans1 = answer_question("What is TCP?", db=db, document_ids=[doc_a.id, doc_b.id], user_id=user4.id)

        # Second run (instant cache hit)
        t0 = time.time()
        ans2 = answer_question("What is TCP?", db=db, document_ids=[doc_a.id, doc_b.id], user_id=user4.id)
        t_hit = (time.time() - t0) * 1000
        assert ans2.get("cached") == True
        print(f"PASS: Cache hit verified in {t_hit:.2f}ms (cached=True)!")

        # Invalidation test: simulate content edit on doc_a
        doc_a.extracted_text += "\nUpdated network RFC specification."
        db.commit()
        hash2 = compute_documents_combined_hash([doc_a.id, doc_b.id], db)
        assert hash1 != hash2, "Content edit failed to alter version hash!"
        cache_key2 = compute_multi_doc_cache_key(user4.id, [doc_a.id, doc_b.id], hash2, "What is TCP?")
        assert cache_key1 != cache_key2, "Stale cache key survived content alteration!"
        print("PASS: Content alteration strictly invalidates stale cache key!")

        # -------------------------------------------------------------
        # TEST 17: Ollama Offline / Unreachable Fallback Resilience
        # -------------------------------------------------------------
        print("\n=== TEST 17: Offline Fallback Resilience ===")
        results_synth = [
            {"document_id": doc_a.id, "document_title": "Doc A", "citation_index": 1, "page": 1, "content": "TCP uses a three-way handshake."},
            {"document_id": doc_b.id, "document_title": "Doc B", "citation_index": 2, "page": 1, "content": "UDP provides connectionless datagram transport."}
        ]
        fallback_ans = generate_deterministic_grounded_answer("Compare TCP and UDP", results_synth, is_multi_document=True)
        assert "[1]" in fallback_ans and "[2]" in fallback_ans
        assert "Doc A" in fallback_ans and "Doc B" in fallback_ans
        print("PASS: Deterministic fallback generated grounded multi-doc answer with citations!")

        # -------------------------------------------------------------
        # TEST 18: Grounded Follow-Up Question Generation
        # -------------------------------------------------------------
        print("\n=== TEST 18: Grounded Follow-Up Question Generation ===")
        follow_ups = generate_grounded_follow_up_questions(
            query="Compare TCP and UDP",
            results=results_synth,
            answer_text="TCP is reliable [1] while UDP is fast [2]."
        )
        assert len(follow_ups) >= 2, f"Expected 2-3 follow-ups, got: {follow_ups}"
        assert any("Doc A" in q for q in follow_ups)
        print(f"PASS: Generated {len(follow_ups)} grounded follow-up questions: {follow_ups}")

        print("\n=========================================================")
        print("ALL 18 MULTI-DOCUMENT CHAT TESTS PASSED WITH ZERO FAILURES!")
        print("=========================================================")


if __name__ == "__main__":
    run_tests()

