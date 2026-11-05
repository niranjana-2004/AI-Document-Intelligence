import sys
import os
import json
from pathlib import Path

# Add backend directory to path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.handwritten_page import HandwrittenPage
from create_ground_truth import GROUND_TRUTH_PAGES
from benchmark_ocr import calculate_cer, calculate_wer, levenshtein_distance

def evaluate():
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == 12).first()
        if not doc:
            print("Document 12 not found!")
            return

        pages = db.query(HandwrittenPage).filter(HandwrittenPage.document_id == 12).order_by(HandwrittenPage.page_number).all()
        
        report = {
            "document_id": doc.id,
            "filename": doc.filename,
            "subject": doc.subject,
            "pages": []
        }

        all_gt_chars = 0
        all_gt_words = 0
        all_raw_char_dist = 0
        all_raw_word_dist = 0
        all_edited_char_dist = 0
        all_edited_word_dist = 0
        
        all_confidences = []

        for p in pages:
            gt = GROUND_TRUTH_PAGES.get(p.page_number, "").strip()
            raw = (p.raw_transcription or "").strip()
            edited = (p.edited_transcription or "").strip()

            gt_chars = len(gt)
            gt_words = len(gt.split())

            raw_c_dist = levenshtein_distance(list(gt), list(raw))
            raw_w_dist = levenshtein_distance(gt.split(), raw.split())
            raw_cer = raw_c_dist / gt_chars if gt_chars else 0
            raw_wer = raw_w_dist / gt_words if gt_words else 0

            edited_c_dist = levenshtein_distance(list(gt), list(edited))
            edited_w_dist = levenshtein_distance(gt.split(), edited.split())
            edited_cer = edited_c_dist / gt_chars if gt_chars else 0
            edited_wer = edited_w_dist / gt_words if gt_words else 0

            all_gt_chars += gt_chars
            all_gt_words += gt_words
            all_raw_char_dist += raw_c_dist
            all_raw_word_dist += raw_w_dist
            all_edited_char_dist += edited_c_dist
            all_edited_word_dist += edited_w_dist

            lines_meta = p.ocr_metadata.get("lines", []) if p.ocr_metadata else []
            confs = [l.get("confidence", 0.0) for l in lines_meta if "confidence" in l]
            if confs:
                all_confidences.extend(confs)

            p_data = {
                "page_number": p.page_number,
                "confidence_score": p.confidence_score,
                "lines_detected": len(lines_meta),
                "empty_failed_lines": sum(1 for l in lines_meta if not l.get("text", "").strip()),
                "avg_line_conf": round(sum(confs)/len(confs), 2) if confs else 0.0,
                "min_line_conf": min(confs) if confs else 0.0,
                "max_line_conf": max(confs) if confs else 0.0,
                "raw_cer": round(raw_cer, 4),
                "raw_wer": round(raw_wer, 4),
                "raw_c_dist": raw_c_dist,
                "raw_w_dist": raw_w_dist,
                "edited_cer": round(edited_cer, 4),
                "edited_wer": round(edited_wer, 4),
                "gt_chars": gt_chars,
                "gt_words": gt_words,
                "raw_lines": [l.get("text", "") for l in lines_meta],
                "raw_text": raw,
                "edited_text": edited,
                "structured_layout": p.ocr_metadata.get("structured_layout", {}) if p.ocr_metadata else {}
            }
            report["pages"].append(p_data)

        report["overall"] = {
            "total_pages": len(pages),
            "total_gt_chars": all_gt_chars,
            "total_gt_words": all_gt_words,
            "raw_cer": round(all_raw_char_dist / all_gt_chars, 4),
            "raw_wer": round(all_raw_word_dist / all_gt_words, 4),
            "edited_cer": round(all_edited_char_dist / all_gt_chars, 4),
            "edited_wer": round(all_edited_word_dist / all_gt_words, 4),
            "total_lines": len(all_confidences),
            "avg_conf": round(sum(all_confidences)/len(all_confidences), 2) if all_confidences else 0.0,
            "min_conf": min(all_confidences) if all_confidences else 0.0,
            "max_conf": max(all_confidences) if all_confidences else 0.0
        }

        with open("evaluate_results.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        print("Evaluation extracted successfully to evaluate_results.json!")
        print(f"Overall Raw CER: {report['overall']['raw_cer']*100:.2f}%, WER: {report['overall']['raw_wer']*100:.2f}%")
        print(f"Overall Edited CER: {report['overall']['edited_cer']*100:.2f}%, WER: {report['overall']['edited_wer']*100:.2f}%")

    finally:
        db.close()

if __name__ == "__main__":
    evaluate()

