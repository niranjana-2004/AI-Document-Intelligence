"""
Performance Profiling Script for Knowledge Graph Pipeline.

Measures each individual stage separately:
- document loading
- text/chunk assembly
- candidate concept extraction
- candidate deduplication
- sentence construction
- candidate relationship generation
- evidence lookup
- relationship verification
- graph persistence
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from app.models.document import Document
from app.models.knowledge_graph import ensure_knowledge_graph_schema
from app.models.user import User
from app.services.knowledge_graph_evidence_service import (
    assemble_substantive_document_units,
    build_sentence_spans,
)
from app.services.knowledge_graph_extraction_service import extract_grounded_nodes
from app.services.knowledge_graph_relationship_service import build_grounded_relationships
from app.services.knowledge_graph_repository import replace_knowledge_graph
from app.services.knowledge_graph_service import _compute_stats, _effective_content_hash
from test_db_isolation import isolated_test_db


def profile_document(doc_id: int) -> Dict[str, Any]:
    with isolated_test_db(clone_dev_db=True) as (db, _, _):
        ensure_knowledge_graph_schema(db.get_bind())
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            return {"error": f"Doc {doc_id} not found"}

        metrics: Dict[str, Any] = {
            "document_id": doc.id,
            "filename": doc.filename,
            "document_type": doc.document_type,
            "is_handwritten": bool(doc.is_handwritten),
        }

        # 1. Text & Chunk Assembly
        t0 = time.perf_counter()
        raw_units, substantive_units, section_hierarchy, pages_count, base_hash = (
            assemble_substantive_document_units(doc, db)
        )
        effective_hash = _effective_content_hash(doc, db, base_hash)
        metrics["t_assembly_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        metrics["raw_units"] = len(raw_units)
        metrics["substantive_units"] = len(substantive_units)
        metrics["pages_count"] = pages_count

        # 2. Sentence Construction
        t0 = time.perf_counter()
        spans = build_sentence_spans(substantive_units)
        metrics["t_sentence_construction_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        metrics["sentence_spans_count"] = len(spans)

        # 3. Candidate Concept Extraction & Deduplication & Grounding
        t0 = time.perf_counter()
        extraction = extract_grounded_nodes(
            document=doc,
            db=db,
            units=substantive_units,
            spans=spans,
            section_hierarchy=section_hierarchy,
            max_nodes=32,
        )
        metrics["t_node_extraction_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        nodes = extraction["nodes"]
        metrics["node_count"] = len(nodes)
        metrics["extraction_diagnostics"] = extraction["diagnostics"]

        # 4. Candidate Relationship Generation & Evidence Lookup
        t0 = time.perf_counter()
        rel_result = build_grounded_relationships(
            nodes=nodes,
            spans=spans,
            units=substantive_units,
            used_research_analysis=extraction["used_research_analysis"],
            skip_llm=True,
        )
        metrics["t_relationship_and_evidence_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        all_edges = rel_result["edges"]
        metrics["edge_count"] = len(all_edges)
        metrics["rel_diagnostics"] = rel_result["diagnostics"]

        # 5. Graph Persistence
        t0 = time.perf_counter()
        visible_edges = [e for e in all_edges if float(e["confidence"]) >= 0.50]
        stats = _compute_stats(
            nodes,
            all_edges,
            visible_edges,
            used_research_analysis=extraction["used_research_analysis"],
            is_handwritten=bool(doc.is_handwritten),
        )
        replace_knowledge_graph(
            db,
            user_id=doc.user_id,
            document_id=doc.id,
            content_hash=effective_hash,
            graph_version="kg-v1",
            status="ready" if nodes else "empty",
            generation_method=rel_result["generation_method"],
            stats=stats,
            diagnostics={**extraction["diagnostics"], **rel_result["diagnostics"]},
            nodes_payload=nodes,
            edges_payload=all_edges,
        )
        metrics["t_persistence_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        total_ms = (
            metrics["t_assembly_ms"]
            + metrics["t_sentence_construction_ms"]
            + metrics["t_node_extraction_ms"]
            + metrics["t_relationship_and_evidence_ms"]
            + metrics["t_persistence_ms"]
        )
        metrics["total_elapsed_s"] = round(total_ms / 1000, 3)

        return metrics


if __name__ == "__main__":
    for did in [12, 13, 2, 5]:
        res = profile_document(did)
        diag = res.get("rel_diagnostics", {})
        print(f"=== Doc #{did} ({res.get('filename')}) ===", flush=True)
        print(f"  Assembly:               {res.get('t_assembly_ms')} ms", flush=True)
        print(f"  Sentences:              {res.get('t_sentence_construction_ms')} ms ({res.get('sentence_spans_count')} spans)", flush=True)
        print(f"  Concept Ext & Dedup:    {res.get('t_node_extraction_ms')} ms ({res.get('node_count')} nodes)", flush=True)
        print(f"  Rel Gen & Evidence:     {res.get('t_relationship_and_evidence_ms')} ms ({res.get('edge_count')} edges)", flush=True)
        print(f"  Persistence:            {res.get('t_persistence_ms')} ms", flush=True)
        print(f"  Total Time:             {res.get('total_elapsed_s')} s", flush=True)
        print(f"  Candidate Pairs:        raw={diag.get('raw_candidate_pairs')}, filtered={diag.get('filtered_candidate_pairs')}, verified={diag.get('verified_pairs')}, accepted={diag.get('accepted_edges')}, rejected_evidence_free={diag.get('rejected_evidence_free_pairs')}", flush=True)
        print("", flush=True)

