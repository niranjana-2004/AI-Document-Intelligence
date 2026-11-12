"""
Real-Document Validation Script for Knowledge Graph Phase 1.

Runs isolated end-to-end validation against cloned Cognidocs documents inside
`isolated_test_db(clone_dev_db=True)`, ensuring zero mutation to `backend/documents.db`.

Outputs structured JSON metrics to:
  backend/benchmarks/knowledge_graph_results.json
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from fastapi.testclient import TestClient

from app.core.database import DB_PATH
from app.core.security import create_access_token
from app.main import app
from app.models.document import Document
from app.models.knowledge_graph import ensure_knowledge_graph_schema
from app.models.user import User
from app.services.handwriting.ollama_client import check_ollama_health
from test_db_isolation import isolated_test_db


def _db_row_counts(db_path: Path) -> Dict[str, int]:
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        convs = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        rpa = conn.execute("SELECT COUNT(*) FROM research_paper_analyses").fetchone()[0]
        return {"documents": docs, "conversations": convs, "research_paper_analyses": rpa}
    finally:
        conn.close()


def _summarize_graph(doc: Document, res_json: Dict[str, Any], elapsed_s: float) -> Dict[str, Any]:
    nodes = res_json.get("nodes", [])
    edges = res_json.get("edges", [])
    stats = res_json.get("stats", {})
    return {
        "document_id": doc.id,
        "filename": doc.filename,
        "document_type": doc.document_type,
        "is_handwritten": bool(doc.is_handwritten),
        "elapsed_seconds": round(elapsed_s, 3),
        "status": res_json.get("status"),
        "generation_method": res_json.get("generation_method"),
        "node_count": stats.get("node_count", len(nodes)),
        "edge_count": stats.get("edge_count", len(edges)),
        "hidden_low_confidence_edges": stats.get("hidden_low_confidence_edges", 0),
        "explicit_edges": stats.get("explicit_edges", 0),
        "derived_edges": stats.get("derived_edges", 0),
        "high_confidence_edges": stats.get("high_confidence_edges", 0),
        "medium_confidence_edges": stats.get("medium_confidence_edges", 0),
        "low_confidence_edges": stats.get("low_confidence_edges", 0),
        "average_edge_confidence": stats.get("average_edge_confidence", 0.0),
        "grounded_node_ratio": stats.get("grounded_node_ratio", 0.0),
        "grounded_edge_ratio": stats.get("grounded_edge_ratio", 0.0),
        "used_research_analysis": stats.get("used_research_analysis", False),
        "pages_covered_count": len(stats.get("pages_covered", [])),
        "node_type_counts": stats.get("node_type_counts", {}),
        "relationship_counts": stats.get("relationship_counts", {}),
        "top_nodes": [
            {"label": n["label"], "type": n["node_type"], "ev": n["evidence_count"], "aliases": n["aliases"]}
            for n in nodes[:10]
        ],
        "top_edges": [
            {
                "source": e["source_key"],
                "relationship": e["relationship"],
                "target": e["target_key"],
                "origin": e["origin"],
                "confidence": e["confidence"],
                "pages": e["source_pages"],
            }
            for e in edges[:10]
        ],
        "diagnostics": res_json.get("diagnostics", {}),
    }


def main() -> None:
    before_counts = _db_row_counts(Path(DB_PATH))
    ollama_health = check_ollama_health(force_refresh=True)
    ollama_live = ollama_health.get("status") == "connected"

    target_doc_ids: List[int] = [12, 13, 2, 5, 1, 3]
    results: List[Dict[str, Any]] = []
    live_ollama_result: Dict[str, Any] = {}
    lifecycle_checks: Dict[str, Any] = {}

    with isolated_test_db(clone_dev_db=True) as (db, _, _):
        ensure_knowledge_graph_schema(db.get_bind())
        client = TestClient(app)
        if True:
            for doc_id in target_doc_ids:
                doc = db.query(Document).filter(Document.id == doc_id).first()
                if not doc:
                    continue
                owner = db.query(User).filter(User.id == doc.user_id).first()
                if not owner:
                    continue
                token = create_access_token({"sub": str(owner.id)})
                headers = {"Authorization": f"Bearer {token}"}

                t0 = time.perf_counter()
                post_res = client.post(
                    f"/documents/{doc.id}/knowledge-graph",
                    json={"skip_llm": True, "max_nodes": 32},
                    headers=headers,
                )
                elapsed = time.perf_counter() - t0
                if post_res.status_code != 200:
                    results.append({"document_id": doc.id, "error": post_res.text})
                    continue

                payload = post_res.json()
                results.append(_summarize_graph(doc, payload, elapsed))

                if doc.id == 12:
                    # Verify cache hit, GET, regenerate, delete on handwritten networking notes
                    t_get = time.perf_counter()
                    get_res = client.get(f"/documents/{doc.id}/knowledge-graph", headers=headers)
                    get_ms = round((time.perf_counter() - t_get) * 1000, 2)

                    regen_res = client.post(
                        f"/documents/{doc.id}/knowledge-graph/regenerate",
                        json={"skip_llm": True},
                        headers=headers,
                    )
                    del_res = client.delete(f"/documents/{doc.id}/knowledge-graph", headers=headers)
                    after_del = client.get(f"/documents/{doc.id}/knowledge-graph", headers=headers)

                    lifecycle_checks = {
                        "document_id": doc.id,
                        "get_cached_status": get_res.status_code,
                        "get_cached_flag": get_res.json().get("cached") if get_res.status_code == 200 else None,
                        "get_cached_ms": get_ms,
                        "regenerate_status": regen_res.status_code,
                        "regenerate_cached_flag": regen_res.json().get("cached") if regen_res.status_code == 200 else None,
                        "delete_status": del_res.status_code,
                        "after_delete_get_status": after_del.status_code,
                    }

                    if ollama_live:
                        t_llm = time.perf_counter()
                        llm_res = client.post(
                            f"/documents/{doc.id}/knowledge-graph",
                            json={"skip_llm": False, "force_refresh": True, "max_nodes": 24},
                            headers=headers,
                        )
                        llm_elapsed = time.perf_counter() - t_llm
                        if llm_res.status_code == 200:
                            live_ollama_result = _summarize_graph(doc, llm_res.json(), llm_elapsed)

    after_counts = _db_row_counts(Path(DB_PATH))
    report = {
        "benchmark": "knowledge_graph_phase1_real_documents",
        "dev_db_before": before_counts,
        "dev_db_after": after_counts,
        "dev_db_untouched": before_counts == after_counts,
        "ollama_health": ollama_health,
        "real_document_results": results,
        "lifecycle_checks": lifecycle_checks,
        "live_ollama_hybrid_result": live_ollama_result or {"skipped": True, "reason": "Ollama not running locally during script execution"},
    }

    out_path = Path(__file__).resolve().parent / "knowledge_graph_results.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote benchmark results to {out_path}")
    print(f"Dev DB untouched: {report['dev_db_untouched']} (before={before_counts}, after={after_counts})")
    for row in results:
        print(
            f"  Doc #{row.get('document_id')} ({row.get('filename')}): "
            f"nodes={row.get('node_count')}, edges={row.get('edge_count')}, "
            f"avg_conf={row.get('average_edge_confidence')}, "
            f"grounded={row.get('grounded_node_ratio')}/{row.get('grounded_edge_ratio')}, "
            f"time={row.get('elapsed_seconds')}s"
        )


if __name__ == "__main__":
    main()

