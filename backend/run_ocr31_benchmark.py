import sys
import os
import time
import json
import re
from typing import Dict, List, Any, Tuple, Optional

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
        # Match case-insensitively with boundary
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

        print(f"Starting 3.1 Technical Recovery OCR on Document #{doc.id} ({doc.filename})...")
        t0 = time.time()
        _run_ocr_for_document(doc, db)
        elapsed = time.time() - t0
        print(f"Document #12 re-transcribed with 3.1 pipeline in {elapsed:.2f}s!")

        pages = db.query(HandwrittenPage).filter(HandwrittenPage.document_id == 12).order_by(HandwrittenPage.page_number).all()

        total_gt_chars = 0
        total_gt_words = 0
        total_raw_c_dist = 0
        total_raw_w_dist = 0
        total_edited_c_dist = 0
        total_edited_w_dist = 0

        page_reports = []
        all_raw_text = []
        all_edited_text = []

        total_corrections_count = 0
        total_accepted_count = 0
        total_suggested_count = 0

        for p in pages:
            gt = GROUND_TRUTH_PAGES.get(p.page_number, "").strip()
            raw = (p.raw_transcription or "").strip()
            edited = (p.edited_transcription or "").strip()

            all_raw_text.append(raw)
            all_edited_text.append(edited)

            gt_chars = len(gt)
            gt_words = len(gt.split())

            raw_c = levenshtein_distance(list(gt), list(raw))
            raw_w = levenshtein_distance(gt.split(), raw.split())
            ed_c = levenshtein_distance(list(gt), list(edited))
            ed_w = levenshtein_distance(gt.split(), edited.split())

            total_gt_chars += gt_chars
            total_gt_words += gt_words
            total_raw_c_dist += raw_c
            total_raw_w_dist += raw_w
            total_edited_c_dist += ed_c
            total_edited_w_dist += ed_w

            meta = p.ocr_metadata or {}
            corrs = meta.get("technical_corrections", [])
            total_corrections_count += len(corrs)
            total_accepted_count += sum(1 for c in corrs if c.get("status") == "accepted")
            total_suggested_count += sum(1 for c in corrs if c.get("status") == "suggested")

            page_reports.append({
                "page_number": p.page_number,
                "lines_count": len(meta.get("lines", [])),
                "confidence": p.confidence_score,
                "raw_cer": round(raw_c / gt_chars, 4),
                "raw_wer": round(raw_w / gt_words, 4),
                "edited_cer": round(ed_c / gt_chars, 4),
                "edited_wer": round(ed_w / gt_words, 4),
                "corrections": corrs
            })

            print(f"Page {p.page_number}: Raw CER={raw_c/gt_chars*100:.2f}%, Recovered CER={ed_c/gt_chars*100:.2f}%, Recovered WER={ed_w/gt_words*100:.2f}% | Corrs={len(corrs)}")

        overall_raw_cer = total_raw_c_dist / total_gt_chars
        overall_raw_wer = total_raw_w_dist / total_gt_words
        overall_edited_cer = total_edited_c_dist / total_gt_chars
        overall_edited_wer = total_edited_w_dist / total_gt_words

        full_raw = "\n".join(all_raw_text)
        full_edited = "\n".join(all_edited_text)

        raw_terms_matched = benchmark_technical_terms(full_raw)
        edited_terms_matched = benchmark_technical_terms(full_edited)

        print("\n================ TECHNICAL TERMINOLOGY RECOVERY EVALUATION ================")
        for term in TARGET_TERMS:
            r_match = raw_terms_matched[term]
            e_match = edited_terms_matched[term]
            status_str = "RECOVERED" if (not r_match and e_match) else ("PRESERVED" if (r_match and e_match) else "MISSED")
            print(f"  * {term:30s} | Raw: {str(r_match):5s} -> Recovered: {str(e_match):5s} [{status_str}]")

        raw_tech_acc = sum(1 for v in raw_terms_matched.values() if v) / len(TARGET_TERMS)
        edited_tech_acc = sum(1 for v in edited_terms_matched.values() if v) / len(TARGET_TERMS)

        print(f"\nTechnical Terms Accuracy: 3.0 Raw = {raw_tech_acc*100:.1f}% -> 3.1 Recovered = {edited_tech_acc*100:.1f}%")
        print(f"Overall CER: 3.0 Raw = {overall_raw_cer*100:.2f}% -> 3.1 Recovered = {overall_edited_cer*100:.2f}%")
        print(f"Overall WER: 3.0 Raw = {overall_raw_wer*100:.2f}% -> 3.1 Recovered = {overall_edited_wer*100:.2f}%")

        benchmark_data = {
            "overall": {
                "raw_cer": round(overall_raw_cer, 4),
                "raw_wer": round(overall_raw_wer, 4),
                "edited_cer": round(overall_edited_cer, 4),
                "edited_wer": round(overall_edited_wer, 4),
                "raw_tech_accuracy": round(raw_tech_acc, 4),
                "recovered_tech_accuracy": round(edited_tech_acc, 4),
                "total_corrections": total_corrections_count,
                "accepted_corrections": total_accepted_count,
                "suggested_corrections": total_suggested_count,
                "total_lines": sum(pr["lines_count"] for pr in page_reports)
            },
            "technical_terms": {
                term: {
                    "raw": raw_terms_matched[term],
                    "recovered": edited_terms_matched[term]
                }
                for term in TARGET_TERMS
            },
            "pages": page_reports
        }

        with open("benchmark_31_results.json", "w", encoding="utf-8") as f:
            json.dump(benchmark_data, f, indent=2)

        print("Results successfully saved to benchmark_31_results.json!")

    finally:
        db.close()

if __name__ == "__main__":
    main()
