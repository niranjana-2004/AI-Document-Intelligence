"""
Experiment 2 & 3: Suspicious Token Benchmark & Hybrid Escalation Simulation.
Evaluates TrOCR Small vs TrOCR Base on difficult handwritten tokens across 7 error categories:
A. Word boundaries
B. Character confusion
C. Ordinary word recognition
D. Technical terminology
E. Punctuation
F. Numbers
G. Small text
Includes image evidence crop persistence and selective Base escalation simulation.
"""

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
from ocr_evaluation.models import (
    load_trocr_small,
    load_trocr_base,
    run_single_inference,
    unload_model,
    SMALL_MODEL_NAME,
    BASE_MODEL_NAME
)
from ocr_evaluation.metrics import (
    classify_token_result,
    classify_three_way,
    compute_confidence_calibration,
    BENCHMARK_TARGET_TERMS
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# Curated dataset of difficult/suspicious tokens from Document #12 with verified ground truth
BENCHMARK_TOKENS_SPECS = [
    # --- Category D: Technical Terminology (15 Benchmark Terms) ---
    {"page": 1, "line": 1, "gt": "TCP", "category": "Technical terminology", "approx_bbox": [1474, 289, 250, 105], "note": "Header TCP"},
    {"page": 1, "line": 2, "gt": "TCP", "category": "Technical terminology", "approx_bbox": [204, 394, 250, 82], "note": "Section title TCP"},
    {"page": 1, "line": 2, "gt": "SYN", "category": "Technical terminology", "approx_bbox": [921, 394, 250, 82], "note": "Section title SYN"},
    {"page": 1, "line": 2, "gt": "SYN flood", "category": "Technical terminology", "approx_bbox": [921, 394, 512, 82], "note": "Merged title SYN flood"},
    {"page": 1, "line": 3, "gt": "DoS", "category": "Technical terminology", "approx_bbox": [1433, 476, 200, 89], "note": "Parenthetical DoS"},
    {"page": 1, "line": 3, "gt": "DDoS", "category": "Technical terminology", "approx_bbox": [1633, 476, 210, 89], "note": "Parenthetical DDoS"},
    {"page": 1, "line": 5, "gt": "SYN", "category": "Technical terminology", "approx_bbox": [684, 644, 267, 92], "note": "Handshake SYN"},
    {"page": 1, "line": 5, "gt": "ACK", "category": "Technical terminology", "approx_bbox": [1378, 644, 267, 92], "note": "Handshake ACK"},
    {"page": 1, "line": 5, "gt": "TCP", "category": "Technical terminology", "approx_bbox": [1645, 644, 160, 92], "note": "Line-end TCP"},
    {"page": 1, "line": 19, "gt": "Transmission Control Block", "category": "Technical terminology", "approx_bbox": [550, 1820, 850, 85], "note": "Expansion Transmission Control Block"},
    {"page": 1, "line": 19, "gt": "TCB", "category": "Technical terminology", "approx_bbox": [1400, 1820, 180, 85], "note": "Parenthetical TCB"},
    {"page": 1, "line": 20, "gt": "backlog queue", "category": "Technical terminology", "approx_bbox": [204, 1905, 450, 85], "note": "Resource backlog queue"},
    {"page": 2, "line": 11, "gt": "SYN cookies", "category": "Technical terminology", "approx_bbox": [204, 1140, 420, 85], "note": "Mitigation SYN cookies"},
    {"page": 2, "line": 18, "gt": "TCP session hijacking", "category": "Technical terminology", "approx_bbox": [204, 1720, 750, 85], "note": "Section title TCP session hijacking"},
    {"page": 4, "line": 13, "gt": "TCP RST attack", "category": "Technical terminology", "approx_bbox": [204, 1310, 520, 85], "note": "Section title TCP RST attack"},
    {"page": 4, "line": 14, "gt": "RST", "category": "Technical terminology", "approx_bbox": [450, 1395, 180, 85], "note": "Header flag RST"},
    {"page": 5, "line": 19, "gt": "RFC 5961", "category": "Technical terminology", "approx_bbox": [880, 1810, 320, 85], "note": "Mitigation standard RFC 5961"},
    {"page": 6, "line": 2, "gt": "TCP ACK flood", "category": "Technical terminology", "approx_bbox": [204, 385, 520, 85], "note": "Section title TCP ACK flood"},

    # --- Category A: Word Boundaries (Merged cursive & split tokens) ---
    {"page": 1, "line": 2, "gt": "TCP Attacks", "category": "Word boundaries", "approx_bbox": [204, 394, 615, 82], "note": "Small merged 'ICCP.Attacks'"},
    {"page": 1, "line": 2, "gt": "Flood", "category": "Word boundaries", "approx_bbox": [1150, 394, 280, 82], "note": "Small read 'INGLOOD'"},
    {"page": 1, "line": 5, "gt": "SYN-ACK", "category": "Word boundaries", "approx_bbox": [951, 644, 427, 92], "note": "Hyphenated ligature SYN-ACK"},
    {"page": 1, "line": 16, "gt": "SYN packets", "category": "Word boundaries", "approx_bbox": [206, 1571, 419, 83], "note": "Small read 'I'll packets'"},
    {"page": 2, "line": 2, "gt": "fills up", "category": "Word boundaries", "approx_bbox": [750, 380, 280, 80], "note": "Cursive boundary fills up"},

    # --- Category B: Character Confusion (Cursive Ambiguity Pairs) ---
    {"page": 2, "line": 2, "gt": "fills", "category": "Character confusion", "approx_bbox": [750, 380, 170, 80], "note": "P/f confusion ('Pills' vs 'fills')"},
    {"page": 1, "line": 4, "gt": "TCP", "category": "Character confusion", "approx_bbox": [1201, 565, 95, 79], "note": "T/V confusion ('TV' vs 'TCP')"},
    {"page": 1, "line": 5, "gt": "ACK", "category": "Character confusion", "approx_bbox": [1378, 644, 267, 92], "note": "A/H confusion ('HCED' vs 'ACK')"},
    {"page": 1, "line": 19, "gt": "TCB", "category": "Character confusion", "approx_bbox": [1400, 1820, 180, 85], "note": "D/B confusion ('TBD' vs 'TCB')"},
    {"page": 1, "line": 17, "gt": "fake", "category": "Character confusion", "approx_bbox": [1200, 1650, 160, 80], "note": "t/k confusion ('fate' vs 'fake')"},
    {"page": 1, "line": 22, "gt": "even", "category": "Character confusion", "approx_bbox": [1350, 2070, 160, 80], "note": "n/r confusion ('ever' vs 'even')"},
    {"page": 1, "line": 17, "gt": "spoofed", "category": "Character confusion", "approx_bbox": [880, 1650, 280, 80], "note": "p/pp confusion ('supposed' vs 'spoofed')"},

    # --- Category C: Ordinary Word Recognition (Academic Handwriting) ---
    {"page": 1, "line": 17, "gt": "usually", "category": "Ordinary word recognition", "approx_bbox": [550, 1650, 250, 80], "note": "Ordinary adverb usually"},
    {"page": 1, "line": 17, "gt": "with", "category": "Ordinary word recognition", "approx_bbox": [780, 1650, 140, 80], "note": "Ordinary preposition with ('write')"},
    {"page": 1, "line": 18, "gt": "allocates", "category": "Ordinary word recognition", "approx_bbox": [650, 1735, 280, 80], "note": "Academic verb allocates"},
    {"page": 1, "line": 6, "gt": "reserve", "category": "Ordinary word recognition", "approx_bbox": [1250, 730, 240, 80], "note": "Academic verb reserve"},
    {"page": 1, "line": 10, "gt": "genuine", "category": "Ordinary word recognition", "approx_bbox": [980, 1060, 260, 80], "note": "Ordinary adjective genuine"},
    {"page": 1, "line": 10, "gt": "users", "category": "Ordinary word recognition", "approx_bbox": [1250, 1060, 180, 80], "note": "Ordinary noun users ('Insecs')"},
    {"page": 2, "line": 1, "gt": "times", "category": "Ordinary word recognition", "approx_bbox": [880, 290, 180, 80], "note": "Ordinary noun times"},
    {"page": 3, "line": 18, "gt": "monitors", "category": "Ordinary word recognition", "approx_bbox": [650, 1720, 260, 80], "note": "Academic verb monitors"},
    {"page": 4, "line": 10, "gt": "hygiene", "category": "Ordinary word recognition", "approx_bbox": [520, 1050, 240, 80], "note": "Ordinary noun hygiene"},
    {"page": 5, "line": 9, "gt": "broken", "category": "Ordinary word recognition", "approx_bbox": [1120, 960, 220, 80], "note": "Ordinary adjective broken"},
    {"page": 5, "line": 14, "gt": "middleboxes", "category": "Ordinary word recognition", "approx_bbox": [850, 1380, 340, 80], "note": "Technical noun middleboxes"},

    # --- Category E: Punctuation (Delimiters, Parentheses, Pen Flicks) ---
    {"page": 1, "line": 5, "gt": "(SYN, SYN-ACK, ACK).", "category": "Punctuation", "approx_bbox": [684, 644, 960, 92], "note": "Parenthetical list with closing paren"},
    {"page": 1, "line": 17, "gt": "(fake)", "category": "Punctuation", "approx_bbox": [1150, 1650, 240, 80], "note": "Parenthetical delimiter (fake)"},
    {"page": 1, "line": 19, "gt": "(TCB)", "category": "Punctuation", "approx_bbox": [1380, 1820, 220, 85], "note": "Unclosed paren repair (TCB)"},
    {"page": 3, "line": 2, "gt": "user's", "category": "Punctuation", "approx_bbox": [920, 380, 200, 80], "note": "Apostrophe flick user's ('user'')"},
    {"page": 4, "line": 2, "gt": "TLS/SSL,", "category": "Punctuation", "approx_bbox": [680, 380, 280, 80], "note": "Slash and comma punctuation"},

    # --- Category F: Numbers & Alphanumeric Identifiers ---
    {"page": 1, "line": 1, "gt": "21BIT042", "category": "Numbers", "approx_bbox": [761, 289, 713, 105], "note": "Alphanumeric roll number 21BIT042"},
    {"page": 1, "line": 2, "gt": "1.", "category": "Numbers", "approx_bbox": [819, 394, 102, 82], "note": "Section number 1."},
    {"page": 2, "line": 15, "gt": "38", "category": "Numbers", "approx_bbox": [1320, 1480, 120, 80], "note": "BCP standard number 38"},
    {"page": 5, "line": 19, "gt": "5961", "category": "Numbers", "approx_bbox": [1050, 1810, 160, 85], "note": "RFC standard number 5961"},

    # --- Category G: Small Text (Superscript, Marginal, Small Parentheticals) ---
    {"page": 1, "line": 1, "gt": "Niranjana", "category": "Small text", "approx_bbox": [203, 289, 458, 105], "note": "Student header name"},
    {"page": 1, "line": 3, "gt": "(DoS/DDoS)", "category": "Small text", "approx_bbox": [1400, 476, 440, 89], "note": "Small parenthetical acronym"},
    {"page": 2, "line": 15, "gt": "(BCP 38)", "category": "Small text", "approx_bbox": [1180, 1480, 280, 80], "note": "Small technical standard reference"}
]


def run_suspicious_token_benchmark(save_crops: bool = True) -> Dict[str, Any]:
    """
    Run Experiment 2 & 3:
    - Crops every suspicious token image from preprocessed document pages.
    - Runs TrOCR Small and TrOCR Base on the token crop.
    - Classifies predictions: CORRECT, INCORRECT, PARTIAL, EMPTY.
    - Performs Three-Way classification: Base wins, Small wins, Both correct, Both incorrect, Ambiguous.
    - Computes Error Category Breakdown (A-G).
    - Computes Confidence Calibration in 5 buckets.
    - Simulates Hybrid Escalation (Small baseline + Base on suspicious tokens).
    """
    db = SessionLocal()
    try:
        pages_cache = {}
        crops_dir = os.path.join(os.path.dirname(__file__), "token_crops")
        if save_crops:
            os.makedirs(crops_dir, exist_ok=True)

        logger.info(f"Loaded {len(BENCHMARK_TOKENS_SPECS)} curated suspicious benchmark token specifications.")

        # Extract token crops from database page images
        token_crops_data = []
        for idx, spec in enumerate(BENCHMARK_TOKENS_SPECS):
            p_num = spec["page"]
            if p_num not in pages_cache:
                p_obj = db.query(HandwrittenPage).filter(
                    HandwrittenPage.document_id == 12,
                    HandwrittenPage.page_number == p_num
                ).first()
                if not p_obj:
                    raise RuntimeError(f"Page {p_num} not found in database!")
                img_path = os.path.join(backend_dir, p_obj.processed_image_path)
                pages_cache[p_num] = Image.open(img_path).convert("RGB")

            p_img = pages_cache[p_num]
            w, h = p_img.size

            bx, by, bw, bh = spec["approx_bbox"]
            # Add safe padding to prevent cutting off cursive descenders
            pad_x = 10
            pad_y = 6
            x1 = max(0, bx - pad_x)
            y1 = max(0, by - pad_y)
            x2 = min(w, bx + bw + pad_x)
            y2 = min(h, by + bh + pad_y)

            crop = p_img.crop((x1, y1, x2, y2))
            crop_path = None
            if save_crops:
                crop_path = os.path.join(crops_dir, f"token_{idx+1:03d}_{spec['gt'].replace('/', '_')}.png")
                crop.save(crop_path)

            token_crops_data.append({
                "token_id": idx + 1,
                "page": p_num,
                "line": spec["line"],
                "ground_truth": spec["gt"],
                "category": spec["category"],
                "note": spec.get("note", ""),
                "crop": crop,
                "crop_path": crop_path
            })

        # ---------------------------------------------------------------------
        # Run TrOCR Small on Token Crops
        # ---------------------------------------------------------------------
        logger.info(f"--- Running TrOCR Small on {len(token_crops_data)} token crops ---")
        s_model, s_proc, _ = load_trocr_small()
        small_token_preds = []

        for item in token_crops_data:
            res = run_single_inference(s_model, s_proc, item["crop"], num_beams=4, max_new_tokens=24)
            small_token_preds.append({
                "pred": res["text"],
                "confidence": res["confidence"],
                "time_ms": res["inference_time_ms"]
            })

        unload_model(s_model, s_proc)
        logger.info("TrOCR Small token inference complete.")

        # ---------------------------------------------------------------------
        # Run TrOCR Base on Token Crops
        # ---------------------------------------------------------------------
        logger.info(f"--- Running TrOCR Base on {len(token_crops_data)} token crops ---")
        b_model, b_proc, _ = load_trocr_base()
        base_token_preds = []

        for item in token_crops_data:
            res = run_single_inference(b_model, b_proc, item["crop"], num_beams=4, max_new_tokens=24)
            base_token_preds.append({
                "pred": res["text"],
                "confidence": res["confidence"],
                "time_ms": res["inference_time_ms"]
            })

        unload_model(b_model, b_proc)
        logger.info("TrOCR Base token inference complete.")

        # ---------------------------------------------------------------------
        # Classify & Compare Outcomes
        # ---------------------------------------------------------------------
        comparison_records = []
        three_way_counts = {
            "Base wins": 0,
            "Small wins": 0,
            "Both correct": 0,
            "Both incorrect": 0,
            "Ambiguous": 0
        }
        category_stats = {}

        for item, s_pred, b_pred in zip(token_crops_data, small_token_preds, base_token_preds):
            gt = item["ground_truth"]
            cat = item["category"]

            s_res = classify_token_result(gt, s_pred["pred"])
            b_res = classify_token_result(gt, b_pred["pred"])
            outcome = classify_three_way(s_res, b_res)
            three_way_counts[outcome] += 1

            if cat not in category_stats:
                category_stats[cat] = {
                    "total": 0,
                    "small_correct": 0,
                    "base_correct": 0,
                    "base_wins": 0,
                    "small_wins": 0
                }
            category_stats[cat]["total"] += 1
            if s_res == "CORRECT":
                category_stats[cat]["small_correct"] += 1
            if b_res == "CORRECT":
                category_stats[cat]["base_correct"] += 1
            if outcome == "Base wins":
                category_stats[cat]["base_wins"] += 1
            elif outcome == "Small wins":
                category_stats[cat]["small_wins"] += 1

            comparison_records.append({
                "token_id": item["token_id"],
                "page": item["page"],
                "line": item["line"],
                "ground_truth": gt,
                "category": cat,
                "note": item["note"],
                "small_prediction": s_pred["pred"],
                "base_prediction": b_pred["pred"],
                "small_confidence": s_pred["confidence"],
                "base_confidence": b_pred["confidence"],
                "small_time_ms": s_pred["time_ms"],
                "base_time_ms": b_pred["time_ms"],
                "small_result": s_res,
                "base_result": b_res,
                "outcome": outcome,
                "crop_path": item["crop_path"]
            })

        total_tokens = len(comparison_records)
        small_correct_total = sum(1 for r in comparison_records if r["small_result"] == "CORRECT")
        base_correct_total = sum(1 for r in comparison_records if r["base_result"] == "CORRECT")

        # Percentages
        three_way_pcts = {
            k: round((v / total_tokens) * 100.0, 2)
            for k, v in three_way_counts.items()
        }

        # ---------------------------------------------------------------------
        # Confidence Calibration Analysis
        # ---------------------------------------------------------------------
        small_calib_inputs = [
            {"confidence": r["small_confidence"], "is_correct": (r["small_result"] == "CORRECT")}
            for r in comparison_records
        ]
        base_calib_inputs = [
            {"confidence": r["base_confidence"], "is_correct": (r["base_result"] == "CORRECT")}
            for r in comparison_records
        ]
        small_calibration = compute_confidence_calibration(small_calib_inputs)
        base_calibration = compute_confidence_calibration(base_calib_inputs)

        # ---------------------------------------------------------------------
        # Experiment 3: Hybrid Escalation Simulation
        # ---------------------------------------------------------------------
        # Escalation criteria: Token has Small confidence < 70.0% OR Small was flagged as suspicious
        escalated_records = []
        hybrid_correct_count = 0
        total_additional_cpu_ms = 0.0

        for r in comparison_records:
            # Check if this token would trigger escalation under OCR 3.3 criteria
            is_suspicious_for_small = (r["small_confidence"] < 70.0 or r["small_result"] != "CORRECT")
            if is_suspicious_for_small:
                # Escalate to Base
                escalated_records.append(r)
                total_additional_cpu_ms += r["base_time_ms"]
                is_hybrid_correct = (r["base_result"] == "CORRECT")
            else:
                # Keep Small
                is_hybrid_correct = (r["small_result"] == "CORRECT")

            if is_hybrid_correct:
                hybrid_correct_count += 1

        escalated_count = len(escalated_records)
        escalation_pct = round((escalated_count / total_tokens) * 100.0, 2)
        small_acc = round((small_correct_total / total_tokens) * 100.0, 2)
        base_acc = round((base_correct_total / total_tokens) * 100.0, 2)
        hybrid_acc = round((hybrid_correct_count / total_tokens) * 100.0, 2)
        accuracy_delta = round(hybrid_acc - small_acc, 2)
        avg_additional_ms_per_token = round(total_additional_cpu_ms / total_tokens, 1)

        # Build category results with percentages
        for cat, data in category_stats.items():
            t = data["total"]
            data["small_acc_pct"] = round((data["small_correct"] / t) * 100.0, 1) if t > 0 else 0.0
            data["base_acc_pct"] = round((data["base_correct"] / t) * 100.0, 1) if t > 0 else 0.0

        results = {
            "total_benchmark_tokens": total_tokens,
            "overall_accuracy": {
                "small_accuracy_pct": small_acc,
                "base_accuracy_pct": base_acc,
                "small_correct_count": small_correct_total,
                "base_correct_count": base_correct_total,
                "net_accuracy_delta": round(base_acc - small_acc, 2)
            },
            "three_way_classification": {
                "counts": three_way_counts,
                "percentages": three_way_pcts
            },
            "category_analysis": category_stats,
            "performance": {
                "small_avg_time_ms": round(sum(r["small_time_ms"] for r in comparison_records) / total_tokens, 1),
                "base_avg_time_ms": round(sum(r["base_time_ms"] for r in comparison_records) / total_tokens, 1),
                "token_slowdown_factor": round(
                    (sum(r["base_time_ms"] for r in comparison_records) / total_tokens) /
                    (sum(r["small_time_ms"] for r in comparison_records) / total_tokens),
                    2
                )
            },
            "confidence_calibration": {
                "small": small_calibration,
                "base": base_calibration
            },
            "hybrid_escalation_simulation": {
                "escalated_token_count": escalated_count,
                "escalation_percentage": escalation_pct,
                "small_baseline_accuracy_pct": small_acc,
                "hybrid_accuracy_pct": hybrid_acc,
                "accuracy_improvement_pct": accuracy_delta,
                "total_additional_cpu_ms": round(total_additional_cpu_ms, 1),
                "avg_additional_ms_per_token": avg_additional_ms_per_token
            },
            "tokens": comparison_records
        }

        output_path = os.path.join(os.path.dirname(__file__), "token_comparison_results.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        logger.info(f"Suspicious token comparison results saved to {output_path}")
        return results

    finally:
        db.close()


if __name__ == "__main__":
    res = run_suspicious_token_benchmark(save_crops=True)
    print("\n--- EXPERIMENT 2 & 3 SUMMARY ---")
    print(f"Total Tokens: {res['total_benchmark_tokens']}")
    print(f"Small Accuracy: {res['overall_accuracy']['small_accuracy_pct']}% | Base Accuracy: {res['overall_accuracy']['base_accuracy_pct']}%")
    print("Three-Way Outcome:")
    for k, v in res["three_way_classification"]["percentages"].items():
        print(f"  * {k}: {res['three_way_classification']['counts'][k]} ({v}%)")
    print(f"\nHybrid Escalation Simulation: {res['hybrid_escalation_simulation']['escalation_percentage']}% tokens escalated")
    print(f"Hybrid Accuracy: {res['hybrid_escalation_simulation']['hybrid_accuracy_pct']}% (+{res['hybrid_escalation_simulation']['accuracy_improvement_pct']}% gain)")
    print(f"Avg Added CPU Time per Token: {res['hybrid_escalation_simulation']['avg_additional_ms_per_token']}ms")

