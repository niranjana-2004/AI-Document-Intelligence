from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.document import Document
from app.models.cross_document_knowledge_graph import ensure_cross_document_knowledge_graph_schema
from app.models.knowledge_graph import ensure_knowledge_graph_schema
from app.models.research_paper_analysis import ensure_research_paper_analysis_schema
from app.models.knowledge_intelligence_cache import ensure_knowledge_intelligence_schema
from app.schemas.knowledge_intelligence import KnowledgeIntelligenceQueryRequest
from app.services.knowledge_intelligence_service import execute_knowledge_intelligence_query


def run_benchmark():
    real_db_path = BACKEND_DIR / "documents.db"
    bench_db_path = BACKEND_DIR / "ki_benchmark.db"

    if bench_db_path.exists():
        os.remove(bench_db_path)

    # Clone real database to isolated benchmark copy
    shutil.copyfile(real_db_path, bench_db_path)
    print(f"[Benchmark] Cloned {real_db_path} -> {bench_db_path}")

    engine = create_engine(f"sqlite:///{bench_db_path}")
    Session = sessionmaker(bind=engine)
    ensure_knowledge_graph_schema(engine)
    ensure_cross_document_knowledge_graph_schema(engine)
    ensure_research_paper_analysis_schema(engine)
    ensure_knowledge_intelligence_schema(engine)

    db = Session()
    try:
        # Find real user and documents
        user_id = 4
        docs = db.query(Document).filter(Document.user_id == user_id).all()
        print(f"[Benchmark] User {user_id} owns {len(docs)} real documents")

        doc_map = {d.id: d.filename for d in docs}
        print(f"[Benchmark] Sample Documents: {[(d.id, d.filename, 'handwritten' if d.is_handwritten else d.document_type) for d in docs[:6]]}")

        # Target documents: Doc 12 (Handwritten), Doc 14 (Printed TXT), Doc 5 (Thesis/Research)
        test_doc_ids = [d.id for d in docs if d.id in [12, 14, 5]]
        if len(test_doc_ids) < 2:
            test_doc_ids = [d.id for d in docs[:3]]

        print(f"[Benchmark] Selected test doc IDs: {test_doc_ids} ({[doc_map.get(i) for i in test_doc_ids]})")

        results = []

        # -------------------------------------------------------------
        # 1. Cold Query: Cross-Document Synthesis on TCP (Docs 12, 14)
        # -------------------------------------------------------------
        q1 = "What do my documents say about TCP?"
        req1 = KnowledgeIntelligenceQueryRequest(
            query=q1,
            document_ids=[12, 14] if (12 in doc_map and 14 in doc_map) else test_doc_ids[:2],
            skip_llm=True,  # deterministic synthesis
            force_refresh=True,
        )
        t0 = time.perf_counter()
        res1 = execute_knowledge_intelligence_query(db=db, user_id=user_id, request=req1)
        lat_cold = (time.perf_counter() - t0) * 1000

        print("\n--- QUERY 1 (Cold Cross-Doc Synthesis) ---")
        print(f"Query: {q1}")
        print(f"Direct Answer Snippet: {res1.direct_answer.text[:180]}...")
        print(f"Grounding Status: {res1.direct_answer.grounding_status}")
        print(f"Focus Entities: {res1.focus_entities}")
        print(f"Evidence Excerpts: {len(res1.evidence)}")
        print(f"Insights: {len(res1.cross_document_insights)}")
        print(f"Conflicts: {len(res1.conflicts)}")
        print(f"Cold Latency: {lat_cold:.2f}ms")
        print(f"Cached: {res1.cached}")

        results.append({
            "name": "Cold Query (TCP Cross-Doc)",
            "latency_ms": lat_cold,
            "cached": res1.cached,
            "grounding": res1.direct_answer.grounding_status,
            "evidence_count": len(res1.evidence),
        })

        # -------------------------------------------------------------
        # 2. Warm Query: Same Query (Cache Hit Test)
        # -------------------------------------------------------------
        req2 = KnowledgeIntelligenceQueryRequest(
            query=q1,
            document_ids=[12, 14] if (12 in doc_map and 14 in doc_map) else test_doc_ids[:2],
            skip_llm=True,
            force_refresh=False,
        )
        t0 = time.perf_counter()
        res2 = execute_knowledge_intelligence_query(db=db, user_id=user_id, request=req2)
        lat_warm = (time.perf_counter() - t0) * 1000

        print("\n--- QUERY 2 (Warm Cache Hit) ---")
        print(f"Warm Latency: {lat_warm:.2f}ms")
        print(f"Cached: {res2.cached}")
        speedup = lat_cold / max(0.001, lat_warm)
        print(f"Cache Speedup: {speedup:.1f}x")

        results.append({
            "name": "Warm Query (Cache Hit)",
            "latency_ms": lat_warm,
            "cached": res2.cached,
            "speedup": speedup,
            "grounding": res2.direct_answer.grounding_status,
        })

        # -------------------------------------------------------------
        # 3. Entity Comparison Query: TCP vs UDP
        # -------------------------------------------------------------
        q3 = "Compare TCP and UDP in my documents"
        req3 = KnowledgeIntelligenceQueryRequest(
            query=q3,
            document_ids=[12, 14] if (12 in doc_map and 14 in doc_map) else test_doc_ids[:2],
            skip_llm=True,
        )
        t0 = time.perf_counter()
        res3 = execute_knowledge_intelligence_query(db=db, user_id=user_id, request=req3)
        lat_comp = (time.perf_counter() - t0) * 1000

        print("\n--- QUERY 3 (Comparison Query) ---")
        print(f"Query: {q3}")
        print(f"Intent: {res3.intent}")
        print(f"Focus Entities: {res3.focus_entities}")
        print(f"Grounding Status: {res3.direct_answer.grounding_status}")
        print(f"Latency: {lat_comp:.2f}ms")

        results.append({
            "name": "Comparison Query (TCP vs UDP)",
            "latency_ms": lat_comp,
            "cached": res3.cached,
            "grounding": res3.direct_answer.grounding_status,
        })

        # -------------------------------------------------------------
        # 4. Research/Thesis Query (Doc 5 - Cloud Security)
        # -------------------------------------------------------------
        doc5_id = 5 if 5 in doc_map else test_doc_ids[0]
        q4 = "What are the key security and encryption mechanisms in cloud storage?"
        req4 = KnowledgeIntelligenceQueryRequest(
            query=q4,
            document_ids=[doc5_id],
            skip_llm=True,
        )
        t0 = time.perf_counter()
        res4 = execute_knowledge_intelligence_query(db=db, user_id=user_id, request=req4)
        lat_rpa = (time.perf_counter() - t0) * 1000

        print("\n--- QUERY 4 (Thesis Security Intelligence) ---")
        print(f"Query: {q4}")
        print(f"Focus Entities: {res4.focus_entities}")
        print(f"Evidence Excerpts: {len(res4.evidence)}")
        print(f"Latency: {lat_rpa:.2f}ms")

        results.append({
            "name": "Thesis Security Query",
            "latency_ms": lat_rpa,
            "cached": res4.cached,
            "grounding": res4.direct_answer.grounding_status,
        })

        # -------------------------------------------------------------
        # 5. Adversarial Query: Completely Unknown Concept
        # -------------------------------------------------------------
        q5 = "Explain everything Cognidocs knows about Quantum Teleportation and Tachyon Fields"
        req5 = KnowledgeIntelligenceQueryRequest(
            query=q5,
            document_ids=test_doc_ids,
            skip_llm=True,
        )
        t0 = time.perf_counter()
        res5 = execute_knowledge_intelligence_query(db=db, user_id=user_id, request=req5)
        lat_adv = (time.perf_counter() - t0) * 1000

        print("\n--- QUERY 5 (Adversarial Unknown Concept) ---")
        print(f"Query: {q5}")
        print(f"Grounding Status: {res5.direct_answer.grounding_status}")
        print(f"Direct Answer: {res5.direct_answer.text}")
        assert res5.direct_answer.grounding_status == "insufficient_evidence", "Must reject unknown concept!"

        results.append({
            "name": "Adversarial Unknown Concept",
            "latency_ms": lat_adv,
            "grounding": res5.direct_answer.grounding_status,
        })

        # Summary Table
        print("\n================ BENCHMARK SUMMARY ================")
        for r in results:
            print(f"- {r['name']}: {r['latency_ms']:.1f}ms | Grounding: {r['grounding']} | Cached: {r.get('cached', False)}")
        print("===================================================\n")

    finally:
        db.close()
        engine.dispose()
        if bench_db_path.exists():
            os.remove(bench_db_path)
            print(f"[Benchmark] Cleaned up benchmark DB: {bench_db_path}")


if __name__ == "__main__":
    run_benchmark()

