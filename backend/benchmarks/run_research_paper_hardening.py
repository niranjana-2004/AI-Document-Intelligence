"""
Controlled Hardening & Edge-Case Validation Runner for Research Paper Analyzer (Phase 1)

Evaluates:
1) Real Cognidocs documents from backend/documents.db inside isolated_test_db(clone_dev_db=True)
   (docs #1 resume, #2 journal PDF, #3 DOCX + manual override, #5 160-page thesis, #12 handwritten notes PDF)
   including live local Ollama hybrid test + cache timing when Ollama is running.
2) Explicitly labeled synthetic hardening fixtures covering:
   IEEE two-column, ACM CCS, conference paper, ToC-heavy thesis/paper, structural-number traps,
   figure/table/algorithm/equation refs, minimal paper (missing fields), student assignment,
   business/product documentation, and handwritten note with academic keywords.

Zero mutations are ever made to backend/documents.db.

Outputs:
  backend/benchmarks/research_paper_hardening_results.json
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

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
from app.models.document_chunk import DocumentChunk
from app.models.user import User
from app.schemas.research_paper import MISSING_FIELD_TEXT
from app.services.embedding_services import generate_embedding
from app.services.handwriting.ollama_client import check_ollama_health
from test_db_isolation import isolated_test_db


TOC_LEADER_RE = re.compile(r"(?:\.\s*){4,}|(?:\. ){3,}")
STRUCTURAL_TRAP_NUMBERS = ("3.2", "Page 12", "[18]", "2024", "Eq. (5)", "Figure 4", "Table 2")


def _db_row_counts(db_path: Path) -> Dict[str, int]:
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        convs = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        rpa = conn.execute("SELECT COUNT(*) FROM research_paper_analyses").fetchone()[0]
        return {"documents": docs, "conversations": convs, "research_paper_analyses": rpa}
    finally:
        conn.close()


def _auth_headers(user_id: int) -> Dict[str, str]:
    token = create_access_token({"sub": str(user_id)})
    return {"Authorization": f"Bearer {token}"}


def _seed_fixture(
    db,
    user_id: int,
    filename: str,
    pages: List[Tuple[int, str]],
    doc_type: str = "PDF",
    is_hw: bool = False,
) -> Document:
    full_text = "\n\n".join(txt for _, txt in pages)
    doc = Document(
        user_id=user_id,
        filename=filename,
        document_type=doc_type,
        file_path=f"uploads/hardening/{filename}",
        extracted_text=full_text,
        text_length=len(full_text),
        is_handwritten=is_hw,
        processing_status="completed",
        processing_progress=100,
    )
    db.add(doc)
    db.flush()
    for idx, (pnum, txt) in enumerate(pages):
        db.add(
            DocumentChunk(
                document_id=doc.id,
                chunk_index=idx,
                page_number=pnum,
                content=txt,
                embedding=generate_embedding(txt[:350]),
            )
        )
    db.commit()
    db.refresh(doc)
    return doc


def _count_toc_leaks(data: Dict[str, Any]) -> List[str]:
    leaks: List[str] = []
    for sec in data.get("sections") or []:
        title = sec.get("title") or ""
        if TOC_LEADER_RE.search(title):
            leaks.append(f"section:{title[:80]}")
    for ev_id, ev in (data.get("evidence") or {}).items():
        excerpt = ((ev.get("source") or {}).get("excerpt") or "")
        if TOC_LEADER_RE.search(excerpt) or "3.1 Key Management Services" in excerpt:
            leaks.append(f"evidence:{ev_id}:{excerpt[:80]}")
    for sec_key in ("basic_information", "research_context", "methodology", "evaluation", "conclusion"):
        for k, v in (data.get(sec_key) or {}).items():
            if not isinstance(v, dict):
                continue
            val = v.get("value") or ""
            if TOC_LEADER_RE.search(val) or "3.1 Key Management Services" in val:
                leaks.append(f"field:{sec_key}.{k}:{val[:80]}")
    return leaks


def _audit_case(
    data: Dict[str, Any],
    origin: str,
    category: str,
    wall_ms: float,
    repeat_cached: Any = None,
    cache_wall_ms: Any = None,
    check_structural_traps: bool = False,
) -> Dict[str, Any]:
    doc_id = data.get("document_id")
    pages_count = max(1, int(data.get("pages_count") or 1))
    is_hw = bool(data.get("is_handwritten")) or str(data.get("document_type") or "").upper() == "HANDWRITTEN"

    populated_fields = 0
    grounded_fields = 0
    missing_fields = 0
    fact_types: Dict[str, int] = {"explicit": 0, "derived": 0, "inferred": 0, "missing": 0}
    wrong_nav = 0

    for sec_key in ("basic_information", "research_context", "methodology", "evaluation", "conclusion"):
        for v in (data.get(sec_key) or {}).values():
            if not isinstance(v, dict):
                continue
            ft = v.get("fact_type", "missing")
            fact_types[ft] = fact_types.get(ft, 0) + 1
            if ft == "missing" or v.get("value") == MISSING_FIELD_TEXT:
                missing_fields += 1
            else:
                populated_fields += 1
                srcs = v.get("sources") or []
                if srcs:
                    grounded_fields += 1
                for s in srcs:
                    s_doc = s.get("document_id")
                    s_page = int(s.get("page") or 0)
                    expected_prefix = f"/handwritten/{doc_id}" if is_hw else f"/documents?doc={doc_id}"
                    if s_doc != doc_id or s_page < 1 or s_page > pages_count or not expected_prefix:
                        wrong_nav += 1

    toc_leaks = _count_toc_leaks(data)

    structural_fp: List[str] = []
    if check_structural_traps:
        for item in data.get("numerical_data") or []:
            ov = str(item.get("original_value") or "")
            for trap in STRUCTURAL_TRAP_NUMBERS:
                if trap in ov:
                    structural_fp.append(ov)

    tf_items = (data.get("tables_and_figures") or {}).get("items") or []
    unsupported_visual_claims = sum(1 for x in tf_items if x.get("visually_parsed") is not False)
    if tf_items and not (data.get("tables_and_figures") or {}).get("visual_parsing_limitation"):
        unsupported_visual_claims += 1

    det = data.get("paper_detection") or {}
    return {
        "origin": origin,
        "category": category,
        "document_id": doc_id,
        "filename": data.get("document_filename"),
        "document_type": data.get("document_type"),
        "is_handwritten": is_hw,
        "expected_route_target": f"/handwritten/{doc_id}?page=..." if is_hw else f"/documents?doc={doc_id}&page=...",
        "paper_detection": {
            "is_research_paper": det.get("is_research_paper"),
            "confidence": det.get("confidence"),
            "classification": det.get("classification"),
            "manual_override": det.get("manual_override"),
            "signals": det.get("signals"),
        },
        "analysis_mode": data.get("analysis_mode"),
        "pages_count": pages_count,
        "sections_count": data.get("sections_count"),
        "populated_fields": populated_fields,
        "grounded_fields": grounded_fields,
        "missing_fields": missing_fields,
        "fact_type_counts": fact_types,
        "evidence_count": data.get("evidence_count"),
        "evidence_coverage": data.get("evidence_coverage"),
        "numerical_data_count": len(data.get("numerical_data") or []),
        "numerical_sample": [
            {
                "metric": n.get("metric_name"),
                "value": n.get("original_value"),
                "unit": n.get("unit"),
                "fact_type": n.get("fact_type"),
                "page": (n.get("source") or {}).get("page"),
            }
            for n in (data.get("numerical_data") or [])[:8]
        ],
        "tables_and_figures_count": len(tf_items),
        "tables_and_figures_labels": [x.get("label") for x in tf_items[:8]],
        "safety_checks": {
            "toc_leak_count": len(toc_leaks),
            "toc_leaks": toc_leaks,
            "structural_number_false_positives": structural_fp,
            "unsupported_visual_claim_count": unsupported_visual_claims,
            "wrong_evidence_navigation_count": wrong_nav,
        },
        "timings": data.get("timings"),
        "wall_ms": wall_ms,
        "repeat_post_cached": repeat_cached,
        "cache_wall_ms": cache_wall_ms,
    }


def _build_synthetic_fixtures() -> List[Dict[str, Any]]:
    return [
        {
            "name": "synthetic_ieee_two_column_paper",
            "category": "ieee_two_column",
            "filename": "synthetic_ieee_packetguard.pdf",
            "pages": [
                (
                    1,
                    "PacketGuard: Line-Rate DDoS Mitigation in Programmable Switches\n"
                    "Rohan Kulkarni, Meera Krishnan, David Zhao\n"
                    "Dept. of Electrical Engineering, Stanford University\n"
                    "DOI: 10.1109/TON.2025.998877\n"
                    "Abstract—Software-defined switches struggle under volumetric SYN floods [1]. "
                    "We propose PacketGuard, a P4 stateful sketch pipeline for sub-millisecond mitigation.\n"
                    "Index Terms—P4, DDoS Mitigation, Programmable Data Plane, Sketching\n"
                    "978-1-6654-1234-5/25/$31.00 ©2025 IEEE\n"
                    "I. INTRODUCTION\n"
                    "Volumetric floods exhaust switch TCAM tables within seconds [2]. "
                    "Our objective is bounded-memory SYN tracking at 100 Gbps line rate.",
                ),
                (
                    2,
                    "II. METHODOLOGY\n"
                    "A. Threat Model\n"
                    "We consider spoofed SYN floods from botnets targeting data-center servers.\n"
                    "B. Sketch Pipeline\n"
                    "Evaluated using P4_16 on the CAIDA-2019 dataset containing 500,000 packets.",
                ),
                (
                    3,
                    "III. EXPERIMENTAL RESULTS\n"
                    "Fig. 2(a) and Table II report Precision = 97.4%, Recall = 96.1%, F1-score = 96.7%, "
                    "whereas Count-Min Sketch drops to 88.5% precision.\n"
                    "IV. CONCLUSION\n"
                    "PacketGuard maintains line-rate mitigation. In future work we explore multi-terabit fabrics.\n"
                    "References\n[1] Liu Z. et al., NitroSketch, SIGCOMM 2019.",
                ),
            ],
        },
        {
            "name": "synthetic_acm_ccs_paper",
            "category": "acm_style",
            "filename": "synthetic_acm_verisql.pdf",
            "pages": [
                (
                    1,
                    "VeriSQL: Formally Verified Query Rewriting for Multi-Tenant Databases\n"
                    "Elena Petrova, Marcus Vance\n"
                    "Proceedings of ACM SIGMOD Conference (2025)\n"
                    "ACM ISBN 979-8-4007-1111-2/25/06\n"
                    "Abstract\n"
                    "We present VeriSQL, an SMT-backed query optimizer that prevents cross-tenant row leakage.\n"
                    "CCS CONCEPTS\n• Security and privacy -> Database security.\n"
                    "Keywords: Formal Verification, Multi-Tenant Isolation, SMT",
                ),
                (
                    2,
                    "1 INTRODUCTION\nWe formulate invariant synthesis over relational algebra trees.\n"
                    "2 METHODOLOGY\nOur empirical study evaluates 1,200 TPC-C queries using Z3 in Python.",
                ),
                (
                    3,
                    "3 EVALUATION\nVeriSQL achieves Accuracy = 99.8% with latency = 1.8 ms (p < 0.01).\n"
                    "4 CONCLUSION\nVeriSQL eliminates cross-tenant predicate bugs.\n"
                    "References\n[1] Wang S. et al., Cosette, CIDR 2017.",
                ),
            ],
        },
        {
            "name": "synthetic_toc_and_structural_traps",
            "category": "toc_heavy_and_structural_traps",
            "check_structural_traps": True,
            "filename": "synthetic_toc_traps_paper.pdf",
            "pages": [
                (
                    1,
                    "Table of Contents\n"
                    "Abstract . . . . . . . . . . . . . . . . . . . . . . . . iv\n"
                    "3. Proposed Framework 30 3.1 Key Management Services . . . . . . . . 30 "
                    "3.2 Decentralized Policy Engine . . . . . . . . . . . . . . . . . 34",
                ),
                (
                    2,
                    "NumGuard: Verifying Quantitative Claims Under Structural Noise\n"
                    "Authors: Asha Verma, Kiran Rao\n"
                    "Proceedings of Conference on Empirical NLP (2025)\n"
                    "Abstract\n"
                    "We propose NumGuard to verify numeric reporting accuracy.\n"
                    "1. Introduction\n"
                    "See Section 3.2, Figure 4, Table 2, Page 12, Reference [18], and Eq. (5) from 2024.",
                ),
                (
                    3,
                    "2. Methodology\nWe test 5,000 samples from the GLUE dataset in PyTorch.\n"
                    "3. Results\n"
                    "In Section 3.2 (published 2024), Reference [18] and Figure 3(a), Table II, Eq. (4), Algorithm 1 "
                    "report Accuracy = 87.2%, F1-score = 0.91, p < 0.05, and 95% CI [0.88, 0.94].\n"
                    "4. Conclusion\nNumGuard suppresses structural traps.\n"
                    "References\n[18] Smith J., NeurIPS 2024.",
                ),
            ],
        },
        {
            "name": "synthetic_minimal_missing_fields",
            "category": "missing_fields",
            "filename": "synthetic_minimal_paper.pdf",
            "pages": [
                (
                    1,
                    "Compact Routing in Edge Meshes\nAuthors: Tarun Singh\n"
                    "Abstract\nWe propose MeshRoute to lower hop count in edge clusters.\n"
                    "1. Introduction\nStatic routing causes tail latency spikes.",
                ),
                (
                    2,
                    "2. Methodology\nWe evaluate MeshRoute using simulation.\n"
                    "3. Conclusion\nMeshRoute simplifies convergence.\n"
                    "References\n[1] Stoica I., SIGCOMM 2001.",
                ),
            ],
        },
        {
            "name": "synthetic_student_assignment",
            "category": "non_research_assignment",
            "filename": "cs401_assignment3.pdf",
            "pages": [
                (
                    1,
                    "CS-401 Operating Systems Assignment 3\n"
                    "Student Name: Ananya Das | Course Syllabus\n"
                    "Homework Submission: Implement a round-robin scheduler in C.\n"
                    "Abstract concepts from lectures applied to process queues.",
                )
            ],
        },
        {
            "name": "synthetic_product_documentation",
            "category": "non_research_product_doc",
            "filename": "enterprise_gateway_manual.pdf",
            "pages": [
                (
                    1,
                    "Acme Cloud Gateway - User Manual & API Reference\n"
                    "Installation Guide: Download binary and configure pricing tiers.\n"
                    "Executive Summary: Quarterly Revenue grew 18%.",
                )
            ],
        },
        {
            "name": "synthetic_handwritten_academic_notes",
            "category": "handwritten_notes_safeguard",
            "filename": "lecture_notes_scan.png",
            "doc_type": "HANDWRITTEN",
            "is_hw": True,
            "pages": [
                (
                    1,
                    "Lecture Notes on Abstract Algebra and Research Methodology\n"
                    "References: Chapter 2, Exercise Set B, DOI: 10.1000/note.sample\n"
                    "1. Introduction to groups and rings | Accuracy = 90%",
                )
            ],
        },
    ]


def main() -> int:
    before_counts = _db_row_counts(DB_PATH)
    ollama_status = check_ollama_health(force_refresh=True)
    ollama_ready = ollama_status.get("status") == "connected"

    results: Dict[str, Any] = {
        "dev_db_before": before_counts,
        "ollama_status": ollama_status,
        "real_documents": {},
        "synthetic_fixtures": {},
        "aggregate_metrics": {},
    }

    with isolated_test_db(clone_dev_db=True) as (db, _, _):
        client = TestClient(app)

        # 1) Real Cognidocs documents (det + cache check)
        real_targets = [
            ("doc_2_academic_journal_pdf", 2, {"skip_llm": True}, "journal_article", False),
            ("doc_1_resume_pdf", 1, {"skip_llm": True}, "resume", False),
            ("doc_3_project_report_docx", 3, {"skip_llm": True}, "technical_report", False),
            ("doc_5_thesis_160_pages_pdf", 5, {"skip_llm": True}, "thesis_and_toc_heavy", False),
            ("doc_12_handwritten_notes_pdf", 12, {"skip_llm": True}, "handwritten_notes", False),
        ]

        for label, doc_id, body, category, check_traps in real_targets:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if not doc:
                results["real_documents"][label] = {"error": f"Document {doc_id} not found"}
                continue
            headers = _auth_headers(doc.user_id)
            t0 = time.perf_counter()
            res = client.post(f"/documents/{doc_id}/research-analysis", json=body, headers=headers)
            wall_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            if res.status_code != 200:
                results["real_documents"][label] = {"status_code": res.status_code, "detail": res.text}
                continue
            t_cache = time.perf_counter()
            res_cache = client.post(
                f"/documents/{doc_id}/research-analysis",
                json={"force_refresh": False},
                headers=headers,
            )
            cache_ms = round((time.perf_counter() - t_cache) * 1000.0, 2)
            results["real_documents"][label] = _audit_case(
                res.json(),
                origin="real_cognidocs_db",
                category=category,
                wall_ms=wall_ms,
                repeat_cached=res_cache.json().get("cached") if res_cache.status_code == 200 else None,
                cache_wall_ms=cache_ms,
                check_structural_traps=check_traps,
            )

        # Manual override on real borderline DOCX (doc #3)
        doc3 = db.query(Document).filter(Document.id == 3).first()
        if doc3:
            headers3 = _auth_headers(doc3.user_id)
            t0 = time.perf_counter()
            res_ovr = client.post(
                f"/documents/{doc3.id}/research-analysis",
                json={"classification_override": "research_paper", "skip_llm": True},
                headers=headers3,
            )
            wall_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            if res_ovr.status_code == 200:
                results["real_documents"]["doc_3_manual_override_paper"] = _audit_case(
                    res_ovr.json(),
                    origin="real_cognidocs_db",
                    category="borderline_manual_override",
                    wall_ms=wall_ms,
                )

        # Live Local Ollama hybrid test on real academic PDF (doc #2)
        doc2 = db.query(Document).filter(Document.id == 2).first()
        if doc2 and ollama_ready:
            headers2 = _auth_headers(doc2.user_id)
            t_llm = time.perf_counter()
            res_llm = client.post(
                f"/documents/{doc2.id}/research-analysis",
                json={"force_refresh": True, "skip_llm": False},
                headers=headers2,
            )
            llm_wall_ms = round((time.perf_counter() - t_llm) * 1000.0, 2)
            if res_llm.status_code == 200:
                results["real_documents"]["doc_2_live_ollama_hybrid"] = _audit_case(
                    res_llm.json(),
                    origin="real_cognidocs_db",
                    category="live_local_ollama_hybrid",
                    wall_ms=llm_wall_ms,
                )
            else:
                results["real_documents"]["doc_2_live_ollama_hybrid"] = {
                    "origin": "real_cognidocs_db",
                    "status_code": res_llm.status_code,
                    "detail": res_llm.text,
                    "wall_ms": llm_wall_ms,
                }
        else:
            results["real_documents"]["doc_2_live_ollama_hybrid"] = {
                "origin": "real_cognidocs_db",
                "skipped": True,
                "reason": ollama_status.get("message", "Ollama unavailable"),
            }

        # 2) Synthetic Hardening Fixtures (inside isolated temp DB)
        seed_user = db.query(User).first()
        seed_headers = _auth_headers(seed_user.id)
        for spec in _build_synthetic_fixtures():
            doc = _seed_fixture(
                db,
                seed_user.id,
                spec["filename"],
                spec["pages"],
                doc_type=spec.get("doc_type", "PDF"),
                is_hw=bool(spec.get("is_hw", False)),
            )
            t0 = time.perf_counter()
            res = client.post(
                f"/documents/{doc.id}/research-analysis",
                json={"skip_llm": True},
                headers=seed_headers,
            )
            wall_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            if res.status_code != 200:
                results["synthetic_fixtures"][spec["name"]] = {"status_code": res.status_code, "detail": res.text}
                continue
            results["synthetic_fixtures"][spec["name"]] = _audit_case(
                res.json(),
                origin="synthetic_hardening_fixture",
                category=spec["category"],
                wall_ms=wall_ms,
                check_structural_traps=bool(spec.get("check_structural_traps")),
            )

        # Aggregate safety counters
        all_audited = [
            v for group in (results["real_documents"], results["synthetic_fixtures"])
            for v in group.values()
            if isinstance(v, dict) and "safety_checks" in v
        ]
        results["aggregate_metrics"] = {
            "total_evaluated_runs": len(all_audited),
            "real_document_runs": sum(1 for x in all_audited if x["origin"] == "real_cognidocs_db"),
            "synthetic_fixture_runs": sum(1 for x in all_audited if x["origin"] == "synthetic_hardening_fixture"),
            "toc_false_positive_count": sum(x["safety_checks"]["toc_leak_count"] for x in all_audited),
            "structural_number_false_positive_count": sum(
                len(x["safety_checks"]["structural_number_false_positives"]) for x in all_audited
            ),
            "unsupported_visual_claim_count": sum(
                x["safety_checks"]["unsupported_visual_claim_count"] for x in all_audited
            ),
            "wrong_evidence_navigation_count": sum(
                x["safety_checks"]["wrong_evidence_navigation_count"] for x in all_audited
            ),
        }

    after_counts = _db_row_counts(DB_PATH)
    results["dev_db_after"] = after_counts
    assert before_counts == after_counts, f"Dev DB mutated! {before_counts} -> {after_counts}"

    out_path = Path(__file__).resolve().parent / "research_paper_hardening_results.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Saved hardening results to {out_path}")
    print(json.dumps({
        "dev_db_before": before_counts,
        "dev_db_after": after_counts,
        "ollama_status": ollama_status,
        "aggregate_metrics": results["aggregate_metrics"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

