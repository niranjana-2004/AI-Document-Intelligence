"""
Real-Document Validation Script for Research Paper Analyzer (Phase 1)

Runs Tests A-E + handwritten PDF check against cloned Cognidocs documents inside
an isolated temporary SQLite database (`isolated_test_db`), ensuring zero
pollution to `backend/documents.db`.

Outputs structured JSON metrics to:
  backend/benchmarks/research_paper_analyzer_phase1_results.json
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.core.database import DB_PATH
from app.models.document import Document
from app.models.user import User
from app.schemas.research_paper import MISSING_FIELD_TEXT
from app.services.handwriting.ollama_client import check_ollama_health
from app.main import app
from test_db_isolation import isolated_test_db


def _db_row_counts(db_path: Path) -> Dict[str, int]:
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        convs = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        return {"documents": docs, "conversations": convs}
    finally:
        conn.close()


def _summarize_response(data: Dict[str, Any]) -> Dict[str, Any]:
    sec_fields = {}
    missing_count = 0
    populated_count = 0
    grounded_count = 0
    fact_types: Dict[str, int] = {"explicit": 0, "derived": 0, "inferred": 0, "missing": 0}

    for section_key in ("basic_information", "research_context", "methodology", "evaluation", "conclusion"):
        sec_obj = data.get(section_key) or {}
        sec_fields[section_key] = {}
        for k, v in sec_obj.items():
            if not isinstance(v, dict):
                continue
            ft = v.get("fact_type", "missing")
            fact_types[ft] = fact_types.get(ft, 0) + 1
            if ft == "missing" or v.get("value") == MISSING_FIELD_TEXT:
                missing_count += 1
            else:
                populated_count += 1
                if v.get("sources"):
                    grounded_count += 1
            sec_fields[section_key][k] = {
                "value_preview": (v.get("value") or "")[:160],
                "fact_type": ft,
                "confidence": v.get("confidence"),
                "source_count": len(v.get("sources") or []),
                "first_page": (v.get("sources") or [{}])[0].get("page") if v.get("sources") else None,
            }

    return {
        "document_id": data.get("document_id"),
        "filename": data.get("document_filename"),
        "document_type": data.get("document_type"),
        "is_handwritten": data.get("is_handwritten"),
        "status": data.get("status"),
        "analysis_mode": data.get("analysis_mode"),
        "cached": data.get("cached"),
        "pages_count": data.get("pages_count"),
        "sections_count": data.get("sections_count"),
        "evidence_count": data.get("evidence_count"),
        "evidence_coverage": data.get("evidence_coverage"),
        "evidence_total": len(data.get("evidence") or []),
        "numerical_data_count": len(data.get("numerical_data") or []),
        "numerical_sample": [
            {
                "metric_name": n.get("metric_name"),
                "original_value": n.get("original_value"),
                "unit": n.get("unit"),
                "fact_type": n.get("fact_type"),
                "page": (n.get("source") or {}).get("page"),
            }
            for n in (data.get("numerical_data") or [])[:6]
        ],
        "tables_and_figures_count": len((data.get("tables_and_figures") or {}).get("items") or []),
        "tables_and_figures_sample": [
            {"label": x.get("label"), "kind": x.get("kind"), "page": x.get("page"), "section": x.get("section")}
            for x in ((data.get("tables_and_figures") or {}).get("items") or [])[:6]
        ],
        "visual_parsing_limitation": (data.get("tables_and_figures") or {}).get("visual_parsing_limitation"),
        "paper_detection": data.get("paper_detection"),
        "section_titles_sample": [
            {"title": s.get("title"), "role": s.get("normalized_role"), "p_start": s.get("page_start"), "children": len(s.get("children") or [])}
            for s in (data.get("sections") or [])[:15]
        ],
        "fact_type_counts": fact_types,
        "populated_fields": populated_count,
        "grounded_fields": grounded_count,
        "missing_fields": missing_count,
        "fields": sec_fields,
        "timings": data.get("timings"),
    }


def _auth_headers_for_user(db, user_id: int) -> Dict[str, str]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise RuntimeError(f"User {user_id} not found in isolated DB")
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def main() -> int:
    before_counts = _db_row_counts(DB_PATH)
    ollama_status = check_ollama_health(force_refresh=True)
    ollama_ready = ollama_status.get("status") == "connected"

    results: Dict[str, Any] = {
        "dev_db_before": before_counts,
        "ollama_status": ollama_status,
        "tests": {},
    }

    with isolated_test_db(clone_dev_db=True) as (db, _, _):
        client = TestClient(app)

        target_cases = [
            ("Test_A_real_academic_pdf", 2, {"skip_llm": True}),
            ("Test_B_real_non_research_pdf", 1, {"skip_llm": True}),
            ("Test_C_technical_report_docx", 3, {"skip_llm": True}),
            ("Test_E_long_thesis_160_pages", 5, {"skip_llm": True}),
            ("Test_HW_handwritten_pdf", 12, {"skip_llm": True}),
        ]

        for label, doc_id, body in target_cases:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if not doc:
                results["tests"][label] = {"error": f"Document {doc_id} not found"}
                continue
            headers = _auth_headers_for_user(db, doc.user_id)

            t0 = time.perf_counter()
            res = client.post(f"/documents/{doc_id}/research-analysis", json=body, headers=headers)
            wall_ms = round((time.perf_counter() - t0) * 1000, 2)
            if res.status_code != 200:
                results["tests"][label] = {"status_code": res.status_code, "detail": res.text, "wall_ms": wall_ms}
                continue

            summary = _summarize_response(res.json())
            summary["wall_ms"] = wall_ms

            # Repeat POST + GET cache checks
            t_post2 = time.perf_counter()
            res_post2 = client.post(f"/documents/{doc_id}/research-analysis", json={"force_refresh": False}, headers=headers)
            t_get = time.perf_counter()
            res_get = client.get(f"/documents/{doc_id}/research-analysis", headers=headers)
            get_ms = round((time.perf_counter() - t_get) * 1000, 2)
            post2_ms = round((t_get - t_post2) * 1000, 2)

            summary["repeat_post_cached"] = res_post2.json().get("cached") if res_post2.status_code == 200 else None
            summary["repeat_post_ms"] = post2_ms
            summary["get_cached_status"] = res_get.status_code
            summary["get_cached_ms"] = get_ms
            results["tests"][label] = summary

        # Test C manual override check on doc 3
        doc3 = db.query(Document).filter(Document.id == 3).first()
        if doc3:
            headers3 = _auth_headers_for_user(db, doc3.user_id)
            res_ovr = client.post(
                f"/documents/{doc3.id}/research-analysis",
                json={"classification_override": "research_paper", "skip_llm": True},
                headers=headers3,
            )
            results["tests"]["Test_C_manual_override"] = (
                {
                    "status_code": res_ovr.status_code,
                    "paper_detection": res_ovr.json().get("paper_detection"),
                    "populated_fields": _summarize_response(res_ovr.json())["populated_fields"],
                }
                if res_ovr.status_code == 200
                else {"status_code": res_ovr.status_code, "detail": res_ovr.text}
            )

        # Optional Live Local Ollama hybrid validation on Test A (doc 2)
        doc2 = db.query(Document).filter(Document.id == 2).first()
        if doc2 and ollama_ready:
            headers2 = _auth_headers_for_user(db, doc2.user_id)
            t_llm = time.perf_counter()
            res_llm = client.post(
                f"/documents/{doc2.id}/research-analysis",
                json={"force_refresh": True, "skip_llm": False},
                headers=headers2,
            )
            llm_wall_ms = round((time.perf_counter() - t_llm) * 1000, 2)
            if res_llm.status_code == 200:
                llm_sum = _summarize_response(res_llm.json())
                llm_sum["wall_ms"] = llm_wall_ms
                results["tests"]["Test_A_live_ollama_hybrid"] = llm_sum
            else:
                results["tests"]["Test_A_live_ollama_hybrid"] = {
                    "status_code": res_llm.status_code,
                    "detail": res_llm.text,
                    "wall_ms": llm_wall_ms,
                }
        else:
            results["tests"]["Test_A_live_ollama_hybrid"] = {
                "skipped": True,
                "reason": ollama_status.get("message", "Ollama unavailable"),
            }

        # Auth check on real endpoint
        unauth_res = client.get("/documents/2/research-analysis")
        other_headers = _auth_headers_for_user(db, 4)
        wrong_owner_res = client.post("/documents/2/research-analysis", json={"skip_llm": True}, headers=other_headers)
        results["security_checks"] = {
            "unauthenticated_get_status": unauth_res.status_code,
            "cross_user_post_status": wrong_owner_res.status_code,
        }

    after_counts = _db_row_counts(DB_PATH)
    results["dev_db_after"] = after_counts
    assert before_counts == after_counts, f"Dev DB mutated! {before_counts} -> {after_counts}"

    out_path = Path(__file__).resolve().parent / "research_paper_analyzer_phase1_results.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Saved validation results to {out_path}")
    print(json.dumps({
        "dev_db_before": before_counts,
        "dev_db_after": after_counts,
        "ollama_status": ollama_status,
        "security_checks": results["security_checks"],
        "summary": {
            k: {
                "is_paper": (v.get("paper_detection") or {}).get("is_research_paper"),
                "conf": (v.get("paper_detection") or {}).get("confidence"),
                "cls": (v.get("paper_detection") or {}).get("classification"),
                "sections": v.get("sections_count"),
                "pages": v.get("pages_count"),
                "mode": v.get("analysis_mode"),
                "populated": v.get("populated_fields"),
                "grounded": v.get("grounded_fields"),
                "coverage": v.get("evidence_coverage"),
                "num_data": v.get("numerical_data_count"),
                "tables_figs": v.get("tables_and_figures_count"),
                "wall_ms": v.get("wall_ms"),
            }
            for k, v in results["tests"].items()
            if isinstance(v, dict)
        },
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
