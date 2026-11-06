import sys
import os
import time
import json
import re
import difflib
from typing import Dict, List, Any, Tuple, Optional, Set

backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.handwritten_page import HandwrittenPage
from app.api.routes.handwritten import _run_ocr_for_document
from create_ground_truth import GROUND_TRUTH_PAGES
from benchmark_ocr import calculate_cer, calculate_wer, levenshtein_distance

TARGET_TERMS = [
    "TCP",
    "SYN",
    "ACK",
    "RST",
    "TCB",
    "DoS",
    "DDoS",
    "SYN flood",
    "TCP session hijacking",
    "TCP RST attack",
    "TCP ACK flood",
    "Transmission Control Block",
    "backlog queue",
    "SYN cookies",
    "RFC 5961"
]

def benchmark_technical_terms(text: str) -> Dict[str, bool]:
    results = {}
    for term in TARGET_TERMS:
        pattern = r'\b' + re.escape(term) + r'\b'
        results[term] = bool(re.search(pattern, text, re.IGNORECASE))
    return results

def main():
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == 12).first()
        if not doc:
            print("Doc 12 not found!")
            return

        print(f"Starting 3.3 General Handwriting Accuracy Benchmark on Document #{doc.id} ({doc.filename})...")
        t0 = time.time()
        _run_ocr_for_document(doc, db)
        elapsed = time.time() - t0
        print(f"Document #12 re-transcribed with 3.3 pipeline in {elapsed:.2f}s!")

        pages = db.query(HandwrittenPage).filter(HandwrittenPage.document_id == 12).order_by(HandwrittenPage.page_number).all()

        total_gt_chars = 0
        total_gt_words = 0
        total_raw_c_dist = 0
        total_raw_w_dist = 0
        total_recovered_c_dist = 0
        total_recovered_w_dist = 0

        page_reports = []
        all_raw_text = []
        all_recovered_text = []

        total_corrections_count = 0
        total_accepted_count = 0
        total_suggested_count = 0
        total_rejected_count = 0

        total_tokens_count = 0
        total_suspicious_tokens = 0
        total_word_boundary_splits = 0
        total_parentheticals = 0
        total_punct_corrs = 0
        total_char_corrs = 0

        for p in pages:
            gt = GROUND_TRUTH_PAGES.get(p.page_number, "").strip()
            raw = (p.raw_transcription or "").strip()
            recovered = (p.edited_transcription or "").strip()

            all_raw_text.append(raw)
            all_recovered_text.append(recovered)

            gt_chars = len(gt)
            gt_words = len(gt.split())

            raw_c = levenshtein_distance(list(gt), list(raw))
            raw_w = levenshtein_distance(gt.split(), raw.split())
            rec_c = levenshtein_distance(list(gt), list(recovered))
            rec_w = levenshtein_distance(gt.split(), recovered.split())

            total_gt_chars += gt_chars
            total_gt_words += gt_words
            total_raw_c_dist += raw_c
            total_raw_w_dist += raw_w
            total_recovered_c_dist += rec_c
            total_recovered_w_dist += rec_w

            meta = p.ocr_metadata or {}
            corrs = meta.get("technical_corrections", [])
            tokens = meta.get("tokens", [])

            total_tokens_count += len(tokens)
            total_suspicious_tokens += sum(1 for t in tokens if t.get("is_suspicious"))
            total_word_boundary_splits += sum(1 for c in corrs if c.get("type") == "word_boundary")
            total_parentheticals += sum(1 for c in corrs if c.get("type") == "parenthetical")
            total_punct_corrs += sum(1 for c in corrs if c.get("type") == "punctuation")
            total_char_corrs += sum(1 for c in corrs if c.get("type") == "character")

            total_corrections_count += len(corrs)
            total_accepted_count += sum(1 for c in corrs if c.get("status") == "accepted")
            total_suggested_count += sum(1 for c in corrs if c.get("status") == "suggested")
            total_rejected_count += sum(1 for c in corrs if c.get("status") == "rejected")

            page_reports.append({
                "page_number": p.page_number,
                "lines_count": len(meta.get("lines", [])),
                "tokens_count": len(tokens),
                "confidence": p.confidence_score,
                "raw_cer": round(raw_c / gt_chars, 4),
                "raw_wer": round(raw_w / gt_words, 4),
                "recovered_cer": round(rec_c / gt_chars, 4),
                "recovered_wer": round(rec_w / gt_words, 4),
                "corrections": corrs
            })

            print(f"Page {p.page_number}: Raw CER={raw_c/gt_chars*100:.2f}%, Recovered CER={rec_c/gt_chars*100:.2f}%, Recovered WER={rec_w/gt_words*100:.2f}% | Corrs={len(corrs)} (Acc={sum(1 for c in corrs if c.get('status')=='accepted')}, Sug={sum(1 for c in corrs if c.get('status')=='suggested')})")

        overall_raw_cer = total_raw_c_dist / total_gt_chars
        overall_raw_wer = total_raw_w_dist / total_gt_words
        overall_rec_cer = total_recovered_c_dist / total_gt_chars
        overall_rec_wer = total_recovered_w_dist / total_gt_words

        full_raw = "\n".join(all_raw_text)
        full_recovered = "\n".join(all_recovered_text)

        raw_terms_matched = benchmark_technical_terms(full_raw)
        recovered_terms_matched = benchmark_technical_terms(full_recovered)

        print("\n================ 3.3 TECHNICAL TERMINOLOGY RECOVERY EVALUATION ================")
        term_eval = {}
        for term in TARGET_TERMS:
            r_val = raw_terms_matched[term]
            rec_val = recovered_terms_matched[term]
            status_str = "RECOVERED (3.3)" if (not r_val and rec_val) else ("PRESERVED" if (r_val and rec_val) else "MISSED")
            print(f"  * {term.ljust(30)} | Raw: {str(r_val).ljust(5)} -> 3.3 Recovered: {str(rec_val).ljust(5)} [{status_str}]")
            term_eval[term] = {
                "raw": r_val,
                "recovered": rec_val
            }

        recovered_terms_count = sum(1 for v in recovered_terms_matched.values() if v)
        raw_terms_count = sum(1 for v in raw_terms_matched.values() if v)

        # Precision, Recall, F1 for technical terms
        tp = recovered_terms_count
        fp = 0
        fn = len(TARGET_TERMS) - tp
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        print("\n--- OVERALL METRICS ---")
        print(f"Overall CER: Raw = {overall_raw_cer*100:.2f}% -> 3.3 Recovered = {overall_rec_cer*100:.2f}%")
        print(f"Overall WER: Raw = {overall_raw_wer*100:.2f}% -> 3.3 Recovered = {overall_rec_wer*100:.2f}%")
        print(f"Character Accuracy: Raw = {(1.0 - overall_raw_cer)*100:.2f}% -> 3.3 Recovered = {(1.0 - overall_rec_cer)*100:.2f}%")
        print(f"Word Accuracy: Raw = {(1.0 - overall_raw_wer)*100:.2f}% -> 3.3 Recovered = {(1.0 - overall_rec_wer)*100:.2f}%")
        print(f"Technical Terms Accuracy: Raw = {raw_terms_count/len(TARGET_TERMS)*100:.1f}% -> 3.3 Recovered = {recovered_terms_count/len(TARGET_TERMS)*100:.1f}%")
        print(f"Precision: {precision*100:.1f}%, Recall: {recall*100:.1f}%, F1: {f1*100:.1f}%")
        print(f"Total Tokens Analyzed: {total_tokens_count}")
        print(f"Suspicious Tokens Flagged: {total_suspicious_tokens}")
        print(f"Word Boundary Splits: {total_word_boundary_splits}")
        print(f"Parentheticals Recovered: {total_parentheticals}")
        print(f"Punctuation Recoveries: {total_punct_corrs}")
        print(f"Character Recoveries: {total_char_corrs}")
        print(f"Total Corrections: {total_corrections_count} (Accepted={total_accepted_count}, Suggested={total_suggested_count})")

        benchmark_data = {
            "overall": {
                "raw_cer": round(overall_raw_cer, 4),
                "raw_wer": round(overall_raw_wer, 4),
                "recovered_cer": round(overall_rec_cer, 4),
                "recovered_wer": round(overall_rec_wer, 4),
                "char_accuracy": round(1.0 - overall_rec_cer, 4),
                "word_accuracy": round(1.0 - overall_rec_wer, 4),
                "raw_tech_accuracy": round(raw_terms_count / len(TARGET_TERMS), 4),
                "recovered_tech_accuracy": round(recovered_terms_count / len(TARGET_TERMS), 4),
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
                "total_tokens": total_tokens_count,
                "suspicious_tokens": total_suspicious_tokens,
                "word_boundary_splits": total_word_boundary_splits,
                "parentheticals_recovered": total_parentheticals,
                "punctuation_recovered": total_punct_corrs,
                "character_recovered": total_char_corrs,
                "total_corrections": total_corrections_count,
                "accepted_corrections": total_accepted_count,
                "suggested_corrections": total_suggested_count,
                "execution_time_seconds": round(elapsed, 2)
            },
            "technical_terms": term_eval,
            "pages": page_reports
        }

        with open("benchmark_33_results.json", "w", encoding="utf-8") as f:
            json.dump(benchmark_data, f, indent=2)

        print("\nBenchmark results saved to backend/benchmark_33_results.json!")

    finally:
        db.close()

if __name__ == "__main__":
    main()

