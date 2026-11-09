import os
import sys
import json
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from app.core.database import SessionLocal
from app.models.user import User
from app.models.document import Document
from app.services.document_comparison_service import compare_documents_service

def run_real_document_validation():
    print("=================================================================")
    print("COGNIDOCS DOCUMENT COMPARISON — REAL DOCUMENT VALIDATION RUNNER")
    print("=================================================================")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "nivivini0602@gmail.com").first()
        if not user:
            print("ERROR: User nivivini0602@gmail.com not found!")
            return

        print(f"Authenticated Test User: {user.email} (ID #{user.id})")

        # Validation Run A: Doc 3 (DOCX Project Report) vs Doc 13 (Handwritten OCR)
        doc_a = db.query(Document).filter(Document.id == 3, Document.user_id == user.id).first()
        doc_b = db.query(Document).filter(Document.id == 13, Document.user_id == user.id).first()

        results_payload = {}

        if doc_a and doc_b:
            print(f"\n[BENCHMARK RUN A] Cross-Modal Comparison:")
            print(f"  Doc A: #{doc_a.id} '{doc_a.filename}' ({doc_a.document_type}, len={doc_a.text_length})")
            print(f"  Doc B: #{doc_b.id} '{doc_b.filename}' ({doc_b.document_type}, is_handwritten={doc_b.is_handwritten})")

            # First run (uncached / computation + LLM)
            t0 = time.time()
            res_a = compare_documents_service(
                user_id=user.id,
                document_a_id=doc_a.id,
                document_b_id=doc_b.id,
                db=db,
                force_refresh=True
            )
            t_first = time.time() - t0
            print(f"  -> First run completed in {t_first:.2f}s")
            print(f"  -> Stats: {res_a['statistics']}")
            print(f"  -> AI Summary: {res_a.get('summary', '')[:120]}...")

            # Second run (cached lookup test)
            t1 = time.time()
            res_a_cached = compare_documents_service(
                user_id=user.id,
                document_a_id=doc_a.id,
                document_b_id=doc_b.id,
                db=db,
                force_refresh=False
            )
            t_cached = time.time() - t1
            print(f"  -> Cached lookup completed in {t_cached * 1000:.1f}ms (Speedup: {t_first/max(t_cached, 0.0001):.1f}x)")
            assert res_a_cached["statistics"] == res_a["statistics"], "Cache integrity mismatch!"

            results_payload["cross_modal_benchmark"] = {
                "doc_a": {"id": doc_a.id, "filename": doc_a.filename, "type": doc_a.document_type},
                "doc_b": {"id": doc_b.id, "filename": doc_b.filename, "is_handwritten": doc_b.is_handwritten},
                "latency_first_run_seconds": round(t_first, 3),
                "latency_cached_ms": round(t_cached * 1000, 2),
                "statistics": res_a["statistics"],
                "ai_summary_preview": res_a.get("summary", ""),
                "key_changes_count": len(res_a.get("key_changes", [])),
                "important_additions_count": len(res_a.get("important_additions", []))
            }

        # Validation Run B: Version Revision Comparison (Base vs Added)
        doc_v1 = db.query(Document).filter(Document.id == 14, Document.user_id == user.id).first()
        doc_v2 = db.query(Document).filter(Document.id == 16, Document.user_id == user.id).first()
        if doc_v1 and doc_v2:
            print(f"\n[BENCHMARK RUN B] Version Revision Diffing:")
            print(f"  Doc V1: #{doc_v1.id} '{doc_v1.filename}'")
            print(f"  Doc V2: #{doc_v2.id} '{doc_v2.filename}'")

            t0 = time.time()
            res_b = compare_documents_service(
                user_id=user.id,
                document_a_id=doc_v1.id,
                document_b_id=doc_v2.id,
                db=db,
                force_refresh=True
            )
            t_b = time.time() - t0
            print(f"  -> Run B completed in {t_b:.2f}s")
            print(f"  -> Stats: {res_b['statistics']}")
            print(f"  -> Added items count: {len(res_b['added'])}")

            results_payload["revision_diff_benchmark"] = {
                "doc_v1": {"id": doc_v1.id, "filename": doc_v1.filename},
                "doc_v2": {"id": doc_v2.id, "filename": doc_v2.filename},
                "latency_seconds": round(t_b, 3),
                "statistics": res_b["statistics"],
                "detected_added_count": len(res_b["added"]),
                "detected_similar_count": len(res_b["similarities"])
            }

        # Save to benchmark directory
        benchmarks_dir = os.path.join(os.path.dirname(__file__), "benchmarks")
        os.makedirs(benchmarks_dir, exist_ok=True)
        json_path = os.path.join(benchmarks_dir, "document_comparison_results.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(results_payload, f, indent=2)

        print(f"\nSaved benchmark metrics to: {json_path}")
        print("REAL DOCUMENT VALIDATION COMPLETE!")

    finally:
        db.close()

if __name__ == "__main__":
    run_real_document_validation()
