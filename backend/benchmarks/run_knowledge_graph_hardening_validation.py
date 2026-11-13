import os
import sys
import json
import time
import copy
from typing import Any, Dict, List

# Ensure backend in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.handwritten_page import HandwrittenPage
from app.models.knowledge_graph import KnowledgeGraph, KnowledgeGraphNode, KnowledgeGraphEdge, ensure_knowledge_graph_schema
from app.schemas.knowledge_graph import ALLOWED_RELATIONSHIPS
from app.services.handwriting.ollama_client import check_ollama_health
from app.services.knowledge_graph_service import (
    get_or_generate_knowledge_graph,
)
from test_db_isolation import isolated_test_db


def audit_edge_evidence(edge: Dict[str, Any], doc: Document, db) -> Dict[str, Any]:
    """Audit evidence for a single edge against strict document provenance rules."""
    src = str(edge.get("source_label") or edge.get("source_key") or "").lower()
    tgt = str(edge.get("target_label") or edge.get("target_key") or "").lower()
    rel = edge["relationship"]
    evidence = edge.get("evidence", [])

    has_ev = len(evidence) >= 1
    rel_valid = rel in ALLOWED_RELATIONSHIPS

    # Check that excerpt mentions both or near
    excerpt_has_source = False
    excerpt_has_target = False
    page_valid = True

    max_page = 1
    if doc.is_handwritten:
        hw_pages = db.query(HandwrittenPage).filter(HandwrittenPage.document_id == doc.id).all()
        if hw_pages:
            max_page = max((p.page_number for p in hw_pages), default=1)
    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).all()
    if chunks:
        max_page = max(max_page, max((c.page_number or 1 for c in chunks), default=1))

    for ev in evidence:
        exc = (ev.get("excerpt") or "").lower()
        if src in exc or any(part in exc for part in src.split()):
            excerpt_has_source = True
        if tgt in exc or any(part in exc for part in tgt.split()):
            excerpt_has_target = True
        if ev.get("page", 1) < 1 or ev.get("page", 1) > max_page:
            page_valid = False

    return {
        "edge": f"{src} --[{rel}]--> {tgt}",
        "relationship_valid": rel_valid,
        "has_evidence": has_ev,
        "excerpt_has_source": excerpt_has_source,
        "excerpt_has_target": excerpt_has_target,
        "page_valid": page_valid,
        "confidence": edge["confidence"],
        "origin": edge["origin"],
        "excerpt_sample": evidence[0]["excerpt"][:100] if evidence else "",
    }


def run_hardening_validation():
    print("=============================================================", flush=True)
    print("COGNIDOCS KNOWLEDGE GRAPH PHASE 1 HARDENING VALIDATION", flush=True)
    print("=============================================================", flush=True)

    # 1. Ollama Health Check
    health = check_ollama_health(force_refresh=True)
    status_str = health.get("status") if isinstance(health, dict) else getattr(health, "status", "unknown")
    msg_str = health.get("message") if isinstance(health, dict) else getattr(health, "message", "")
    lat_val = health.get("latency_ms", 0.0) if isinstance(health, dict) else getattr(health, "latency_ms", 0.0)
    print(f"Ollama Status: {status_str} ({msg_str}) in {lat_val:.1f}ms", flush=True)

    results = {
        "ollama_status": status_str,
        "ollama_latency_ms": lat_val,
        "benchmarks": {},
        "safety_checks": {},
        "evidence_audit": [],
        "node_quality_audit": {},
        "concurrency_validation": {},
    }

    with isolated_test_db(clone_dev_db=True) as (db, _, _):
        ensure_knowledge_graph_schema(db.get_bind())
        test_docs = [
            (12, "Handwritten Notes (text-to-handwriting.pdf)"),
            (2, "Research Paper (Fortifying Cloud Security...)"),
            (3, "Technical Report (Project Report - LLM.docx)"),
            (5, "160-Page Thesis (Subhabrata Rana - Thesis.pdf)"),
        ]

        for did, ddesc in test_docs:
            doc = db.query(Document).filter(Document.id == did).first()
            if not doc:
                print(f"Doc #{did} not found, skipping.", flush=True)
                continue

            print(f"\n--- Testing Doc #{did}: {ddesc} ---", flush=True)

            # Deterministic pass
            t0 = time.perf_counter()
            det_resp = get_or_generate_knowledge_graph(
                db=db,
                user_id=doc.user_id,
                document_id=doc.id,
                force_refresh=True,
                skip_llm=True,
            )
            det_time = round(time.perf_counter() - t0, 3)
            det_graph = det_resp.model_dump() if hasattr(det_resp, "model_dump") else det_resp.dict()

            # Live Ollama pass (skip for huge doc 5 to avoid LLM timeouts, or test with bounded LLM)
            llm_graph = None
            llm_time = 0.0
            if status_str == "connected" and did != 5:
                t0 = time.perf_counter()
                llm_resp = get_or_generate_knowledge_graph(
                    db=db,
                    user_id=doc.user_id,
                    document_id=doc.id,
                    force_refresh=True,
                    skip_llm=False,
                )
                llm_time = round(time.perf_counter() - t0, 3)
                llm_graph = llm_resp.model_dump() if hasattr(llm_resp, "model_dump") else llm_resp.dict()

            bench_entry = {
                "document_id": did,
                "description": ddesc,
                "filename": doc.filename,
                "deterministic": {
                    "time_s": det_time,
                    "nodes": len(det_graph["nodes"]),
                    "edges": len(det_graph["edges"]),
                    "avg_confidence": det_graph["stats"]["average_edge_confidence"],
                    "generation_method": det_graph["generation_method"],
                    "diagnostics": det_graph.get("diagnostics", {}),
                },
            }

            if llm_graph:
                diag = llm_graph.get("diagnostics", {})
                bench_entry["hybrid_llm"] = {
                    "time_s": llm_time,
                    "nodes": len(llm_graph["nodes"]),
                    "edges": len(llm_graph["edges"]),
                    "avg_confidence": llm_graph["stats"]["average_edge_confidence"],
                    "generation_method": llm_graph["generation_method"],
                    "llm_batches": diag.get("llm_batches", 0),
                    "llm_verified_count": diag.get("llm_verified_count", 0),
                    "llm_rejected_ungrounded": diag.get("llm_rejected_ungrounded", 0),
                    "llm_rejected_invalid_rel": diag.get("llm_rejected_invalid_rel", 0),
                    "llm_fallback_used": diag.get("llm_fallback_used", 0),
                    "llm_total_latency_ms": diag.get("llm_total_latency_ms", 0.0),
                    "llm_max_latency_ms": diag.get("llm_max_latency_ms", 0.0),
                }

            results["benchmarks"][f"doc_{did}"] = bench_entry

            print(f"  Deterministic: {det_time}s | Nodes={len(det_graph['nodes'])} | Edges={len(det_graph['edges'])} | AvgConf={det_graph['stats']['average_edge_confidence']}", flush=True)
            if llm_graph:
                llm_diag = llm_graph.get("diagnostics", {})
                print(f"  Hybrid Ollama: {llm_time}s | Nodes={len(llm_graph['nodes'])} | Edges={len(llm_graph['edges'])} | AvgConf={llm_graph['stats']['average_edge_confidence']} | Method={llm_graph['generation_method']} | LLM Verified={llm_diag.get('llm_verified_count')} in {llm_diag.get('llm_total_latency_ms')}ms", flush=True)

            # Sample edges for evidence audit
            target_graph = llm_graph or det_graph
            for edge in target_graph["edges"][:6]:
                audit_res = audit_edge_evidence(edge, doc, db)
                audit_res["document_id"] = did
                results["evidence_audit"].append(audit_res)

        # 2. Node Quality Audit on Doc #12 (Handwritten networking)
        doc12 = db.query(Document).filter(Document.id == 12).first()
        if doc12:
            g12_resp = get_or_generate_knowledge_graph(db=db, user_id=doc12.user_id, document_id=12, skip_llm=True)
            g12 = g12_resp.model_dump() if hasattr(g12_resp, "model_dump") else g12_resp.dict()
            labels_and_aliases = []
            for n in g12["nodes"]:
                labels_and_aliases.append(n["label"].lower())
                labels_and_aliases.extend(a.lower() for a in n.get("aliases", []))
            key_terms = ["tcp", "syn flood", "syn cookies", "tcb", "backlog queue", "denial of service"]
            found_terms = [t for t in key_terms if any(t in l for l in labels_and_aliases)]
            results["node_quality_audit"]["doc_12_expected_terms"] = key_terms
            results["node_quality_audit"]["doc_12_found_terms"] = found_terms
            results["node_quality_audit"]["doc_12_coverage_ratio"] = round(len(found_terms) / len(key_terms), 3)

        # 3. Concurrency / Atomicity Test
        print("\n--- Testing Concurrency / Atomicity ---", flush=True)
        doc2 = db.query(Document).filter(Document.id == 2).first()
        u_id = doc2.user_id if doc2 else 1
        g_first = get_or_generate_knowledge_graph(db=db, user_id=u_id, document_id=2, force_refresh=True, skip_llm=True)
        g_second_resp = get_or_generate_knowledge_graph(db=db, user_id=u_id, document_id=2, force_refresh=True, skip_llm=True)
        g_second = g_second_resp.model_dump() if hasattr(g_second_resp, "model_dump") else g_second_resp.dict()
        # Check DB count of KnowledgeGraph rows for doc 2
        kg_rows = db.query(KnowledgeGraph).filter(KnowledgeGraph.document_id == 2).all()
        node_rows = db.query(KnowledgeGraphNode).filter(KnowledgeGraphNode.document_id == 2).all()
        edge_rows = db.query(KnowledgeGraphEdge).filter(KnowledgeGraphEdge.document_id == 2).all()

        results["concurrency_validation"] = {
            "graphs_in_db": len(kg_rows),
            "nodes_in_db": len(node_rows),
            "edges_in_db": len(edge_rows),
            "clean_replacement": len(kg_rows) == 1 and len(node_rows) == len(g_second["nodes"]),
        }
        print(f"  Concurrency clean replacement: {results['concurrency_validation']['clean_replacement']} (1 graph, {len(node_rows)} nodes)", flush=True)

    # Save results to json
    out_path = os.path.join(BASE_DIR, "benchmarks", "knowledge_graph_hardening_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved hardening results to {out_path}", flush=True)
    return results


if __name__ == "__main__":
    run_hardening_validation()
