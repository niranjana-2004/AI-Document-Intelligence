import json
from pathlib import Path
import sys
import time
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from test_db_isolation import isolated_test_db
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.embedding_services import generate_embedding
from app.services.question_service import MIN_CONFIDENCE_THRESHOLD
from app.services.search_service import semantic_search
from app.services.voice_query_recovery_service import (
    clear_voice_recovery_cache,
    recover_voice_query,
)
from app.services.voice_terminology_service import clear_voice_terminology_cache

BENCH_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = BENCH_DIR / "voice_query_recovery_manifest.json"
RESULTS_JSON_PATH = BENCH_DIR / "voice_query_recovery_results.json"
RESULTS_MD_PATH = BENCH_DIR / "voice_query_recovery.md"


SEED_DOCUMENTS = {
    "seed:net": {
        "user_id": 4,
        "filename": "tcp_security_reference_printed.pdf",
        "subject": "Computer Science & Networking",
        "chunks": [
            (
                1,
                "# TCP Security & Denial of Service Attacks\n"
                "A SYN flood exploits the TCP three-way handshake by sending spoofed SYN packets and exhausting "
                "backlog queues. SYN cookies avoid allocating Transmission Control Block (TCB) state until ACK completion.",
            ),
            (
                2,
                "## TCP RST Attack & ACK Flood\n"
                "In a TCP RST attack, forged RST packets abruptly terminate legitimate connections. Strict RFC 5961 "
                "sequence checks defeat off-path RST spoofing. A TCP ACK flood overwhelms stateful firewalls. "
                "Distributed denial-of-service (DDoS) floods use large botnets.",
            ),
        ],
    },
    "seed:physics": {
        "user_id": 4,
        "filename": "physics_electromagnetism_optics.pdf",
        "subject": "Physics & Engineering",
        "chunks": [
            (
                1,
                "# Electromagnetism\n"
                "Faraday's law states that induced electromotive force (EMF) is proportional to the rate of change "
                "of magnetic flux. A light-emitting diode (LED) emits photons via electron-hole recombination.",
            ),
            (
                2,
                "## Quantum Mechanics\n"
                "The Schrodinger equation governs quantum wavefunctions and stationary energy states in atomic systems.",
            ),
        ],
    },
    "seed:math": {
        "user_id": 4,
        "filename": "applied_mathematics_linear_algebra.pdf",
        "subject": "Mathematics & Statistics",
        "chunks": [
            (
                1,
                "# Differential Equations and Linear Algebra\n"
                "An ordinary differential equation (ODE) depends on a single independent variable, while a "
                "partial differential equation (PDE) involves partial derivatives. "
                "An eigenvector scales by an eigenvalue under linear transformation.",
            ),
            (
                2,
                "## Matrix Factorizations & Trigonometry\n"
                "Singular value decomposition (SVD) factors any matrix into orthogonal components. "
                "In trigonometry, the sine function sin(theta) oscillates with period 2 pi alongside cosine.",
            ),
        ],
    },
}


def _seed_isolated_docs(db) -> dict[str, int]:
    """Seed additional discipline documents purely inside the isolated temporary SQLite snapshot."""
    mapping: dict[str, int] = {}
    for key, spec in SEED_DOCUMENTS.items():
        full_text = "\n\n".join(c for _, c in spec["chunks"])
        doc = Document(
            user_id=spec["user_id"],
            filename=spec["filename"],
            document_type="PDF",
            file_path=spec["filename"],
            extracted_text=full_text,
            text_length=len(full_text),
            is_handwritten=False,
            subject=spec["subject"],
            processing_status="completed",
            processing_progress=100,
        )
        db.add(doc)
        db.flush()
        for idx, (page_num, chunk_text) in enumerate(spec["chunks"]):
            emb = generate_embedding(chunk_text)
            db.add(
                DocumentChunk(
                    document_id=doc.id,
                    chunk_index=idx,
                    category="general",
                    content=chunk_text,
                    embedding=emb,
                    page_number=page_num,
                )
            )
        db.commit()
        mapping[key] = doc.id
    return mapping


def _resolve_doc_ids(doc_ref: Any, seed_map: dict[str, int]) -> list[int]:
    refs = doc_ref if isinstance(doc_ref, list) else [doc_ref]
    ids: list[int] = []
    for r in refs:
        if isinstance(r, str) and r.startswith("real:"):
            ids.append(int(r.split(":", 1)[1]))
        elif isinstance(r, str) and r in seed_map:
            ids.append(seed_map[r])
        elif isinstance(r, int):
            ids.append(r)
    return ids


def _eval_retrieval(query: str, db, user_id: int, doc_ids: list[int], expected_doc_id: int | None, expected_kw: str | None) -> dict[str, Any]:
    t0 = time.perf_counter()
    results = semantic_search(
        query=query,
        db=db,
        document_id=None,
        document_ids=doc_ids if doc_ids else None,
        top_k=5,
        user_id=user_id,
    )
    ms = round((time.perf_counter() - t0) * 1000.0, 2)
    top_score = float(results[0]["final_score"]) if results else 0.0
    top_sim = float(results[0]["similarity"]) if results else 0.0
    meets_gate = bool(results and top_score >= MIN_CONFIDENCE_THRESHOLD)
    doc_hit = (
        any(r["document_id"] == expected_doc_id for r in results)
        if expected_doc_id is not None and results
        else bool(results)
    )
    kw_hit = (
        any(expected_kw.lower() in (r.get("content") or "").lower() for r in results)
        if expected_kw and results
        else bool(results)
    )
    return {
        "top_score": round(top_score, 4),
        "top_similarity": round(top_sim, 4),
        "result_count": len(results),
        "meets_confidence_gate": meets_gate,
        "expected_source_hit": doc_hit and kw_hit,
        "latency_ms": ms,
    }


def main():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    cases = manifest["cases"]

    clear_voice_terminology_cache()
    clear_voice_recovery_cache()

    case_results = []
    with isolated_test_db() as (db, _, _):
        seed_map = _seed_isolated_docs(db)

        for case in cases:
            uid = int(case["user_id"])
            doc_ids = _resolve_doc_ids(case["doc_ref"], seed_map)
            raw = case["raw_transcript"]

            # Measure cold (for first access to a doc scope) and warm (cached) recovery latency
            t0 = time.perf_counter()
            r_cold = recover_voice_query(raw, db=db, user_id=uid, document_ids=doc_ids)
            cold_ms = round((time.perf_counter() - t0) * 1000.0, 2)

            t1 = time.perf_counter()
            r_warm = recover_voice_query(raw, db=db, user_id=uid, document_ids=doc_ids)
            warm_ms = round((time.perf_counter() - t1) * 1000.0, 2)

            decision_match = r_warm.decision == case["expected_decision"]
            transcript_match = r_warm.recovered_transcript == case["expected_recovered"]

            exp_src_id = (
                _resolve_doc_ids(case["expected_source_doc"], seed_map)[0]
                if case.get("expected_source_doc")
                else None
            )
            raw_ret = _eval_retrieval(
                raw, db, uid, doc_ids, exp_src_id, case.get("expected_keyword")
            )
            rec_ret = _eval_retrieval(
                r_warm.recovered_transcript, db, uid, doc_ids, exp_src_id, case.get("expected_keyword")
            )

            case_results.append({
                "id": case["id"],
                "category": case["category"],
                "domain": case["domain"],
                "raw_transcript": raw,
                "expected_decision": case["expected_decision"],
                "actual_decision": r_warm.decision,
                "expected_recovered": case["expected_recovered"],
                "actual_recovered": r_warm.recovered_transcript,
                "confidence": r_warm.confidence,
                "suggestions": [s.suggested_span for s in r_warm.suggestions],
                "decision_match": decision_match,
                "transcript_match": transcript_match,
                "cold_recovery_ms": cold_ms,
                "warm_recovery_ms": warm_ms,
                "cache_hit": r_warm.cache_hit,
                "retrieval_raw": raw_ret,
                "retrieval_recovered": rec_ret,
            })

    # Compute aggregate metrics per Section 23
    total = len(case_results)
    clean_cases = [c for c in case_results if c["category"] == "clean_exact"]
    abstention_cases = [
        c for c in case_results
        if c["category"] in {"ambiguous_abstention", "ordinary_abstention", "out_of_scope_abstention"}
    ]
    distorted_cases = [
        c for c in case_results
        if c not in clean_cases and c not in abstention_cases
    ]

    attempted_recoveries = [c for c in case_results if c["actual_decision"] == "RECOVERED"]
    correct_attempted = [
        c for c in attempted_recoveries if c["transcript_match"] and c["expected_decision"] == "RECOVERED"
    ]
    false_recoveries = [
        c for c in (clean_cases + abstention_cases)
        if c["actual_decision"] == "RECOVERED" or c["actual_recovered"] != c["raw_transcript"]
    ]
    correct_abstentions = [
        c for c in abstention_cases
        if c["actual_recovered"] == c["raw_transcript"] and c["decision_match"]
    ]

    recovery_accuracy = (
        round((len(correct_attempted) / len(attempted_recoveries)) * 100.0, 2)
        if attempted_recoveries
        else 0.0
    )
    distorted_recall = (
        round((len([c for c in distorted_cases if c["transcript_match"] and c["decision_match"]]) / len(distorted_cases)) * 100.0, 2)
        if distorted_cases
        else 0.0
    )
    false_recovery_rate = (
        round((len(false_recoveries) / len(clean_cases + abstention_cases)) * 100.0, 2)
        if (clean_cases + abstention_cases)
        else 0.0
    )
    abstention_rate = (
        round((len(correct_abstentions) / len(abstention_cases)) * 100.0, 2)
        if abstention_cases
        else 0.0
    )

    # Retrieval metrics across distorted cases
    raw_gate_pass = sum(1 for c in distorted_cases if c["retrieval_raw"]["meets_confidence_gate"])
    rec_gate_pass = sum(1 for c in distorted_cases if c["retrieval_recovered"]["meets_confidence_gate"])
    raw_src_hit = sum(1 for c in distorted_cases if c["retrieval_raw"]["expected_source_hit"])
    rec_src_hit = sum(1 for c in distorted_cases if c["retrieval_recovered"]["expected_source_hit"])
    avg_raw_score = round(
        sum(c["retrieval_raw"]["top_score"] for c in distorted_cases) / max(1, len(distorted_cases)),
        4,
    )
    avg_rec_score = round(
        sum(c["retrieval_recovered"]["top_score"] for c in distorted_cases) / max(1, len(distorted_cases)),
        4,
    )
    avg_raw_sim = round(
        sum(c["retrieval_raw"]["top_similarity"] for c in distorted_cases) / max(1, len(distorted_cases)),
        4,
    )
    avg_rec_sim = round(
        sum(c["retrieval_recovered"]["top_similarity"] for c in distorted_cases) / max(1, len(distorted_cases)),
        4,
    )

    warm_latencies = sorted(c["warm_recovery_ms"] for c in case_results)
    avg_warm_ms = round(sum(warm_latencies) / max(1, len(warm_latencies)), 2)
    p95_warm_ms = warm_latencies[min(len(warm_latencies) - 1, int(len(warm_latencies) * 0.95))] if warm_latencies else 0.0
    avg_cold_ms = round(sum(c["cold_recovery_ms"] for c in case_results) / max(1, total), 2)

    summary = {
        "total_queries": total,
        "clean_queries": len(clean_cases),
        "distorted_queries": len(distorted_cases),
        "abstention_queries": len(abstention_cases),
        "attempted_recoveries": len(attempted_recoveries),
        "correct_recoveries": len(correct_attempted),
        "recovery_accuracy_pct": recovery_accuracy,
        "distorted_end_to_end_recall_pct": distorted_recall,
        "false_recoveries": len(false_recoveries),
        "false_recovery_rate_pct": false_recovery_rate,
        "correct_abstentions": len(correct_abstentions),
        "abstention_accuracy_pct": abstention_rate,
        "retrieval_distorted_before_after": {
            "raw_confidence_gate_pass": f"{raw_gate_pass}/{len(distorted_cases)}",
            "recovered_confidence_gate_pass": f"{rec_gate_pass}/{len(distorted_cases)}",
            "raw_expected_source_hit": f"{raw_src_hit}/{len(distorted_cases)}",
            "recovered_expected_source_hit": f"{rec_src_hit}/{len(distorted_cases)}",
            "avg_top_score_raw": avg_raw_score,
            "avg_top_score_recovered": avg_rec_score,
            "avg_top_similarity_raw": avg_raw_sim,
            "avg_top_similarity_recovered": avg_rec_sim,
        },
        "latency_ms": {
            "avg_cold_ms": avg_cold_ms,
            "avg_warm_ms": avg_warm_ms,
            "p95_warm_ms": p95_warm_ms,
            "max_warm_ms": max(warm_latencies) if warm_latencies else 0.0,
        },
    }

    output = {"summary": summary, "cases": case_results}
    RESULTS_JSON_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")

    # Render concise markdown summary report
    md_lines = [
        "# Cognidocs Phase 2 — Controlled Voice Query Recovery Benchmark",
        "",
        "## Summary Metrics",
        "",
        f"- **Total benchmark queries**: `{summary['total_queries']}` (`{summary['clean_queries']}` clean, `{summary['distorted_queries']}` distorted/technical, `{summary['abstention_queries']}` ambiguous/ordinary/out-of-scope)",
        f"- **Recovery accuracy (`correct / attempted`)**: `{summary['correct_recoveries']}/{summary['attempted_recoveries']}` (**{summary['recovery_accuracy_pct']}%**)",
        f"- **Distorted recovery recall**: **{summary['distorted_end_to_end_recall_pct']}%**",
        f"- **False recovery rate**: `{summary['false_recoveries']}/{summary['clean_queries'] + summary['abstention_queries']}` (**{summary['false_recovery_rate_pct']}%**)",
        f"- **Abstention accuracy**: `{summary['correct_abstentions']}/{summary['abstention_queries']}` (**{summary['abstention_accuracy_pct']}%**)",
        "",
        "## Retrieval Impact on Distorted Queries (Raw STT vs. Recovered Query)",
        "",
        f"- **Confidence gate (`>= 0.40`) pass rate**: `{raw_gate_pass}/{len(distorted_cases)}` -> **`{rec_gate_pass}/{len(distorted_cases)}`**",
        f"- **Expected source + term hit rate**: `{raw_src_hit}/{len(distorted_cases)}` -> **`{rec_src_hit}/{len(distorted_cases)}`**",
        f"- **Average top retrieval score**: `{avg_raw_score}` -> **`{avg_rec_score}`**",
        f"- **Average top MiniLM similarity**: `{avg_raw_sim}` -> **`{avg_rec_sim}`**",
        "",
        "## Latency",
        "",
        f"- **Average warm recovery overhead**: **{avg_warm_ms} ms** (p95: **{p95_warm_ms} ms**, max: **{summary['latency_ms']['max_warm_ms']} ms**)",
        f"- **Average cold recovery overhead (incl. doc vocab extraction)**: **{avg_cold_ms} ms**",
        "",
        "## Per-Case Results",
        "",
        "| ID | Domain | Raw Transcript | Recovered Query | Decision | Raw Score | Recovered Score | Warm ms | Pass |",
        "|---|---|---|---|---|---:|---:|---:|---|",
    ]
    for c in case_results:
        passed = "PASS" if (c["decision_match"] and c["transcript_match"]) else "FAIL"
        md_lines.append(
            f"| `{c['id']}` | {c['domain']} | `{c['raw_transcript']}` | `{c['actual_recovered']}` | "
            f"`{c['actual_decision']}` ({c['confidence']:.2f}) | {c['retrieval_raw']['top_score']:.3f} | "
            f"{c['retrieval_recovered']['top_score']:.3f} | {c['warm_recovery_ms']:.1f} | {passed} |"
        )
    RESULTS_MD_PATH.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))
    failures = [c["id"] for c in case_results if not (c["decision_match"] and c["transcript_match"])]
    if failures:
        print("MISMATCHES:", failures)
        sys.exit(1)


if __name__ == "__main__":
    main()

