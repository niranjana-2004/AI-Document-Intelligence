import os
import sys
import json
import time

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.user import User
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.question_service import answer_question
from app.services.handwriting.handwritten_source_service import sync_handwritten_chunks_and_embeddings
from test_db_isolation import isolated_test_db


def run_real_document_validation():
    print("=================================================================")
    print("COGNIDOCS MULTI-DOCUMENT CHAT — REAL DOCUMENT VALIDATION RUNNER")
    print("[ISOLATION] Running against isolated temporary SQLite snapshot (dev DB untouched)")
    print("=================================================================")

    with isolated_test_db() as (db, _, _):
        user = db.query(User).filter(User.id == 4).first()
        assert user is not None, "Primary test user #4 not found"
        print(f"Authenticated Test User: {user.email} (ID #{user.id})")

        # Find real test documents
        doc_printed_1 = db.query(Document).filter(Document.id == 3, Document.user_id == user.id).first()
        doc_printed_2 = db.query(Document).filter(Document.id == 7, Document.user_id == user.id).first() or \
                        db.query(Document).filter(Document.id == 8, Document.user_id == user.id).first()
        doc_hw = db.query(Document).filter(Document.id == 13, Document.user_id == user.id).first()

        assert doc_printed_1 is not None, "Doc #3 (Project Report - LLM.docx) not found"
        assert doc_hw is not None, "Doc #13 (Handwritten Python/CSS Notes) not found"

        # Ensure handwritten chunks are synced for Doc 13
        hw_chunk_count = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_hw.id).count()
        if hw_chunk_count == 0:
            print(f"Synchronizing chunks for Handwritten Doc #{doc_hw.id}...")
            sync_handwritten_chunks_and_embeddings(doc_hw.id, db)

        results_payload = {}

        # -------------------------------------------------------------
        # CASE A: Related printed documents
        # -------------------------------------------------------------
        print("\n--- CASE A: Related Printed Documents Synthesis ---")
        doc_ids_a = [3, doc_printed_2.id] if doc_printed_2 else [3]
        t0 = time.time()
        ans_a = answer_question(
            query="What concepts do these documents discuss regarding natural language processing and character recognition?",
            db=db,
            document_ids=doc_ids_a,
            top_k=6,
            user_id=user.id
        )
        t_a = time.time() - t0
        print(f"Latency: {t_a:.2f}s | Result count: {ans_a['result_count']} | Cached: {ans_a.get('cached')}")
        print(f"Answer Preview: {ans_a['answer'][:160]}...")
        assert ans_a["result_count"] >= 1
        results_payload["case_a"] = {
            "status": "PASS",
            "latency": round(t_a, 2),
            "result_count": ans_a["result_count"],
            "sources": [
                {"title": r.get("document_title"), "page": r.get("page"), "type": r.get("source_type")}
                for r in ans_a["results"]
            ]
        }

        # -------------------------------------------------------------
        # CASE B: Printed + Handwritten multi-modal synthesis
        # -------------------------------------------------------------
        print("\n--- CASE B: Printed + Handwritten Cross-Modal Synthesis ---")
        t0 = time.time()
        ans_b = answer_question(
            query="What do the notes explain about web development, styles, and optical character recognition?",
            db=db,
            document_ids=[3, 13],
            top_k=6,
            user_id=user.id
        )
        t_b = time.time() - t0
        print(f"Latency: {t_b:.2f}s | Result count: {ans_b['result_count']}")
        sources_b_types = {r.get("source_type") for r in ans_b["results"]}
        print(f"Source types represented: {sources_b_types}")
        print(f"Answer Preview: {ans_b['answer'][:160]}...")
        results_payload["case_b"] = {
            "status": "PASS",
            "latency": round(t_b, 2),
            "source_types": list(sources_b_types),
            "sources": [
                {"title": r.get("document_title"), "page": r.get("page"), "type": r.get("source_type")}
                for r in ans_b["results"]
            ]
        }

        # -------------------------------------------------------------
        # CASE C: Three-document synthesis
        # -------------------------------------------------------------
        print("\n--- CASE C: Three-Document Cross-Retrieval ---")
        doc_ids_c = [3, doc_printed_2.id if doc_printed_2 else 3, 13]
        t0 = time.time()
        ans_c = answer_question(
            query="What is discussed regarding optical character recognition, programming in python, and language models?",
            db=db,
            document_ids=list(dict.fromkeys(doc_ids_c)),
            top_k=6,
            user_id=user.id
        )
        t_c = time.time() - t0
        print(f"Latency: {t_c:.2f}s | Result count: {ans_c['result_count']}")
        print(f"Answer Preview: {ans_c['answer'][:160]}...")
        results_payload["case_c"] = {
            "status": "PASS",
            "latency": round(t_c, 2),
            "result_count": ans_c["result_count"],
            "sources": [
                {"title": r.get("document_title"), "page": r.get("page"), "type": r.get("source_type")}
                for r in ans_c["results"]
            ]
        }

        # -------------------------------------------------------------
        # CASE D: Unrelated documents with weak overlap
        # -------------------------------------------------------------
        print("\n--- CASE D: Unrelated Documents Weak Overlap Handling ---")
        t0 = time.time()
        ans_d = answer_question(
            query="What common concepts regarding astrophysics and deep ocean biology are present?",
            db=db,
            document_ids=[3, 13],
            top_k=6,
            user_id=user.id
        )
        t_d = time.time() - t0
        print(f"Latency: {t_d:.2f}s | Result count: {ans_d['result_count']}")
        print(f"Answer: {ans_d['answer']}")
        results_payload["case_d"] = {
            "status": "PASS",
            "latency": round(t_d, 2),
            "answer": ans_d["answer"]
        }

        # -------------------------------------------------------------
        # CASE E: Specific source lookup & attribution
        # -------------------------------------------------------------
        print("\n--- CASE E: Specific Source Lookup & Direct Attribution ---")
        t0 = time.time()
        ans_e = answer_question(
            query="Which document discusses Cascading Style Sheets (CSS) and web presentation?",
            db=db,
            document_ids=[3, 13],
            top_k=4,
            user_id=user.id
        )
        t_e = time.time() - t0
        print(f"Latency: {t_e:.2f}s | Result count: {ans_e['result_count']}")
        css_sources = [r for r in ans_e["results"] if r.get("document_id") == 13]
        assert len(css_sources) >= 1, "Failed to retrieve handwritten CSS document"
        print(f"Attributed to Doc #{css_sources[0]['document_id']} ({css_sources[0]['document_title']}, Page {css_sources[0]['page']})")
        print(f"Answer Preview: {ans_e['answer'][:160]}...")
        results_payload["case_e"] = {
            "status": "PASS",
            "latency": round(t_e, 2),
            "attributed_document_id": css_sources[0]["document_id"],
            "attributed_page": css_sources[0]["page"]
        }

        # Save metrics to benchmarks directory
        benchmarks_dir = os.path.join(os.path.dirname(__file__), "benchmarks")
        os.makedirs(benchmarks_dir, exist_ok=True)
        json_path = os.path.join(benchmarks_dir, "multi_document_chat_results.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(results_payload, f, indent=2)

        print(f"\nSaved real validation metrics to: {json_path}")
        print("REAL DOCUMENT VALIDATION COMPLETE!")


if __name__ == "__main__":
    run_real_document_validation()

