"""
Experiment 1: Full-Line OCR Comparison (TrOCR Small vs TrOCR Base) on Document #12.
Evaluates both models under strictly identical line segmentation, image crops, and decoding beams.
Calculates CER, WER, Character Accuracy, Word Accuracy, Technical Terminology (Precision, Recall, F1),
and inference timing on CPU.
"""

import argparse
import json
import logging
import os
import sys
import time
from typing import Dict, List, Any, Tuple, Optional
from PIL import Image

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.core.database import SessionLocal
from app.models.handwritten_page import HandwrittenPage
from create_ground_truth import GROUND_TRUTH_PAGES
from ocr_evaluation.models import (
    load_trocr_small,
    load_trocr_base,
    run_single_inference,
    unload_model,
    SMALL_MODEL_NAME,
    BASE_MODEL_NAME
)
from ocr_evaluation.metrics import (
    calculate_cer,
    calculate_wer,
    calculate_char_accuracy,
    calculate_word_accuracy,
    benchmark_technical_terms,
    levenshtein_distance,
    compute_confidence_calibration,
    BENCHMARK_TARGET_TERMS
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_full_line_comparison(mode: str = "page1_and_benchmark") -> Dict[str, Any]:
    """
    Run Experiment 1:
    - mode="page1": Evaluates all 23 lines of Page 1.
    - mode="page1_and_benchmark": Evaluates all 23 lines of Page 1 + key benchmark lines across all 7 pages.
    - mode="all": Evaluates all 158 lines across all 7 pages.
    """
    db = SessionLocal()
    try:
        pages = db.query(HandwrittenPage).filter(
            HandwrittenPage.document_id == 12
        ).order_by(HandwrittenPage.page_number).all()

        if not pages:
            raise RuntimeError("Document #12 pages not found in database!")

        # Collect lines to evaluate
        eval_lines = []
        for p in pages:
            lines = p.ocr_metadata.get("lines", []) if p.ocr_metadata else []
            img_rel = p.processed_image_path
            img_abs = os.path.join(backend_dir, img_rel)
            if not os.path.exists(img_abs):
                raise FileNotFoundError(f"Processed image not found: {img_abs}")

            for l in lines:
                l_idx = l.get("line_index", 1)
                should_include = False
                if mode == "all":
                    should_include = True
                elif mode == "page1":
                    should_include = (p.page_number == 1)
                else:  # page1_and_benchmark
                    if p.page_number == 1:
                        should_include = True
                    else:
                        # Include key lines with domain terminology across pages 2-7
                        txt_upper = l.get("text", "").upper()
                        rec_upper = l.get("recovered_text", "").upper()
                        if any(term in txt_upper or term in rec_upper for term in [
                            "TCP", "SYN", "ACK", "RST", "TCB", "DOS", "DDOS", "HIJACK", "COOKIE", "5961", "BACKLOG", "FLOOD", "QUEUE", "SPOOF"
                        ]):
                            should_include = True

                if should_include:
                    eval_lines.append({
                        "page_number": p.page_number,
                        "line_index": l_idx,
                        "bbox": l.get("bbox", [0, 0, 100, 50]),
                        "img_path": img_abs,
                        "recorded_small_text": l.get("text", ""),
                        "recorded_recovered_text": l.get("recovered_text", "")
                    })

        logger.info(f"Loaded {len(eval_lines)} lines for evaluation (mode: {mode}).")

        # Pre-load line crops to ensure 100% identical image inputs
        page_images = {}
        line_crops = []
        for item in eval_lines:
            path = item["img_path"]
            if path not in page_images:
                page_images[path] = Image.open(path).convert("RGB")
            p_img = page_images[path]
            bx, by, bw, bh = item["bbox"]
            w, h = p_img.size
            x1 = max(0, bx)
            y1 = max(0, by)
            x2 = min(w, bx + bw)
            y2 = min(h, by + bh)
            crop = p_img.crop((x1, y1, x2, y2))
            line_crops.append(crop)

        # ---------------------------------------------------------------------
        # Phase 1: Evaluate TrOCR Small
        # ---------------------------------------------------------------------
        logger.info(f"--- Phase 1: Evaluating {SMALL_MODEL_NAME} ---")
        s_model, s_proc, s_load_time = load_trocr_small()
        small_results = []
        s_t0 = time.time()

        for idx, (item, crop) in enumerate(zip(eval_lines, line_crops)):
            res = run_single_inference(s_model, s_proc, crop, num_beams=4, max_new_tokens=96)
            small_results.append({
                "line_idx": item["line_index"],
                "page": item["page_number"],
                "text": res["text"],
                "confidence": res["confidence"],
                "time_ms": res["inference_time_ms"],
                "is_hallucination": res["is_hallucination"]
            })
            if (idx + 1) % 5 == 0 or idx == len(eval_lines) - 1:
                logger.info(f"Small evaluated {idx+1}/{len(eval_lines)} lines ({res['inference_time_ms']:.1f}ms per line).")

        s_total_time = round(time.time() - s_t0, 2)
        unload_model(s_model, s_proc)
        logger.info(f"Small evaluation finished in {s_total_time}s.")

        # ---------------------------------------------------------------------
        # Phase 2: Evaluate TrOCR Base
        # ---------------------------------------------------------------------
        logger.info(f"--- Phase 2: Evaluating {BASE_MODEL_NAME} ---")
        b_model, b_proc, b_load_time = load_trocr_base()
        base_results = []
        b_t0 = time.time()

        for idx, (item, crop) in enumerate(zip(eval_lines, line_crops)):
            res = run_single_inference(b_model, b_proc, crop, num_beams=4, max_new_tokens=96)
            base_results.append({
                "line_idx": item["line_index"],
                "page": item["page_number"],
                "text": res["text"],
                "confidence": res["confidence"],
                "time_ms": res["inference_time_ms"],
                "is_hallucination": res["is_hallucination"]
            })
            if (idx + 1) % 2 == 0 or idx == len(eval_lines) - 1:
                logger.info(f"Base evaluated {idx+1}/{len(eval_lines)} lines ({res['inference_time_ms']:.1f}ms per line).")

        b_total_time = round(time.time() - b_t0, 2)
        unload_model(b_model, b_proc)
        logger.info(f"Base evaluation finished in {b_total_time}s.")

        # ---------------------------------------------------------------------
        # Phase 3: Metrics Calculation
        # ---------------------------------------------------------------------
        # Group lines by page
        pages_included = sorted(list(set(item["page_number"] for item in eval_lines)))
        page_level_metrics = {}

        for p_num in pages_included:
            gt_text = GROUND_TRUTH_PAGES.get(p_num, "").strip()
            s_page_lines = [r["text"] for r in small_results if r["page"] == p_num]
            b_page_lines = [r["text"] for r in base_results if r["page"] == p_num]

            s_text = " ".join(s_page_lines)
            b_text = " ".join(b_page_lines)

            # Only calculate full CER/WER against Ground Truth if Page was evaluated in full (e.g. Page 1)
            is_full_page = (p_num == 1 and len(s_page_lines) == 23)
            p_cer_s = calculate_cer(gt_text, s_text) if is_full_page else None
            p_wer_s = calculate_wer(gt_text, s_text) if is_full_page else None
            p_cer_b = calculate_cer(gt_text, b_text) if is_full_page else None
            p_wer_b = calculate_wer(gt_text, b_text) if is_full_page else None

            page_level_metrics[p_num] = {
                "page_number": p_num,
                "lines_count": len(s_page_lines),
                "is_full_page": is_full_page,
                "small": {
                    "text": s_text,
                    "cer": round(p_cer_s, 4) if p_cer_s is not None else None,
                    "wer": round(p_wer_s, 4) if p_wer_s is not None else None,
                    "char_acc": round(1.0 - p_cer_s, 4) if p_cer_s is not None else None,
                    "word_acc": round(1.0 - p_wer_s, 4) if p_wer_s is not None else None,
                    "avg_conf": round(sum(r["confidence"] for r in small_results if r["page"] == p_num) / len(s_page_lines), 2),
                    "avg_time_ms": round(sum(r["time_ms"] for r in small_results if r["page"] == p_num) / len(s_page_lines), 1)
                },
                "base": {
                    "text": b_text,
                    "cer": round(p_cer_b, 4) if p_cer_b is not None else None,
                    "wer": round(p_wer_b, 4) if p_wer_b is not None else None,
                    "char_acc": round(1.0 - p_cer_b, 4) if p_cer_b is not None else None,
                    "word_acc": round(1.0 - p_wer_b, 4) if p_wer_b is not None else None,
                    "avg_conf": round(sum(r["confidence"] for r in base_results if r["page"] == p_num) / len(b_page_lines), 2),
                    "avg_time_ms": round(sum(r["time_ms"] for r in base_results if r["page"] == p_num) / len(b_page_lines), 1)
                }
            }

        # Aggregate full evaluation text
        all_s_text = " ".join(r["text"] for r in small_results)
        all_b_text = " ".join(r["text"] for r in base_results)

        s_tech = benchmark_technical_terms(all_s_text)
        b_tech = benchmark_technical_terms(all_b_text)

        s_times = [r["time_ms"] for r in small_results]
        b_times = [r["time_ms"] for r in base_results]

        s_avg_time = round(sum(s_times) / len(s_times), 1)
        b_avg_time = round(sum(b_times) / len(b_times), 1)
        s_median_time = round(sorted(s_times)[len(s_times) // 2], 1)
        b_median_time = round(sorted(b_times)[len(b_times) // 2], 1)
        slowdown = round(b_avg_time / s_avg_time, 2) if s_avg_time > 0 else 0.0

        line_comparisons = []
        for item, s_res, b_res in zip(eval_lines, small_results, base_results):
            line_comparisons.append({
                "page": item["page_number"],
                "line_idx": item["line_index"],
                "small_text": s_res["text"],
                "base_text": b_res["text"],
                "small_conf": s_res["confidence"],
                "base_conf": b_res["confidence"],
                "small_time_ms": s_res["time_ms"],
                "base_time_ms": b_res["time_ms"],
                "text_differ": (s_res["text"] != b_res["text"])
            })

        diff_count = sum(1 for lc in line_comparisons if lc["text_differ"])

        summary = {
            "mode": mode,
            "total_lines_evaluated": len(eval_lines),
            "pages_included": pages_included,
            "differing_lines_count": diff_count,
            "differing_lines_pct": round((diff_count / len(eval_lines)) * 100.0, 1),
            "small": {
                "model_name": SMALL_MODEL_NAME,
                "load_time_s": s_load_time,
                "total_time_s": s_total_time,
                "avg_inference_ms": s_avg_time,
                "median_inference_ms": s_median_time,
                "min_inference_ms": min(s_times),
                "max_inference_ms": max(s_times),
                "avg_confidence": round(sum(r["confidence"] for r in small_results) / len(small_results), 1),
                "hallucinations_count": sum(1 for r in small_results if r["is_hallucination"]),
                "empty_count": sum(1 for r in small_results if not r["text"]),
                "technical_terms": s_tech
            },
            "base": {
                "model_name": BASE_MODEL_NAME,
                "load_time_s": b_load_time,
                "total_time_s": b_total_time,
                "avg_inference_ms": b_avg_time,
                "median_inference_ms": b_median_time,
                "min_inference_ms": min(b_times),
                "max_inference_ms": max(b_times),
                "avg_confidence": round(sum(r["confidence"] for r in base_results) / len(base_results), 1),
                "hallucinations_count": sum(1 for r in base_results if r["is_hallucination"]),
                "empty_count": sum(1 for r in base_results if not r["text"]),
                "technical_terms": b_tech
            },
            "performance_slowdown_factor": slowdown,
            "page_level_metrics": page_level_metrics,
            "line_comparisons": line_comparisons
        }

        output_path = os.path.join(os.path.dirname(__file__), "full_line_comparison.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Full-line comparison results successfully saved to {output_path}")
        return summary

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Experiment 1: Full-Line OCR Comparison.")
    parser.add_argument("--mode", choices=["page1", "page1_and_benchmark", "all"], default="page1_and_benchmark")
    args = parser.parse_args()

    results = run_full_line_comparison(mode=args.mode)
    print("\n--- EXPERIMENT 1 SUMMARY ---")
    print(f"Lines evaluated: {results['total_lines_evaluated']}")
    print(f"Small avg time: {results['small']['avg_inference_ms']}ms | Base avg time: {results['base']['avg_inference_ms']}ms (Slowdown: {results['performance_slowdown_factor']}x)")
    print(f"Small Tech Terms F1: {results['small']['technical_terms']['f1']*100:.1f}% | Base Tech Terms F1: {results['base']['technical_terms']['f1']*100:.1f}%")
    if 1 in results["page_level_metrics"] and results["page_level_metrics"][1]["is_full_page"]:
        p1 = results["page_level_metrics"][1]
        print(f"Page 1 Small CER: {p1['small']['cer']*100:.2f}%, WER: {p1['small']['wer']*100:.2f}%")
        print(f"Page 1 Base  CER: {p1['base']['cer']*100:.2f}%, WER: {p1['base']['wer']*100:.2f}%")

