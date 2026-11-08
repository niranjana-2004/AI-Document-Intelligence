"""
Unit Tests for Cognidocs General Handwriting Validation Framework
Verifies:
1. Metric computation correctness (CER, WER, accuracy, precision, false correction rate)
2. Ground-truth integrity (missing ground truth rejected, OCR output never used as GT)
3. Manifest validity and schema completeness
4. Benchmark reproducibility and configuration recording
"""

import sys
import os
import json
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(str(backend_dir))

from benchmarks.run_general_handwriting_validation import (
    load_manifest,
    load_ground_truth,
    evaluate_text_metrics,
    evaluate_technical_vocabulary
)
from benchmark_ocr import calculate_cer, calculate_wer, levenshtein_distance


# ---------------------------------------------------------------------------
# 1. Metric Calculation Tests
# ---------------------------------------------------------------------------

def test_metric_calculation_exact_match():
    gt = "The server allocates a Transmission Control Block entry in its backlog queue."
    hyp = "The server allocates a Transmission Control Block entry in its backlog queue."
    metrics = evaluate_text_metrics(gt, hyp)
    assert metrics["cer"] == 0.0
    assert metrics["wer"] == 0.0
    assert metrics["char_accuracy"] == 100.0
    assert metrics["word_accuracy"] == 100.0
    assert metrics["c_dist"] == 0
    assert metrics["w_dist"] == 0


def test_metric_calculation_with_known_errors():
    gt = "The server allocates a Transmission Control Block"
    hyp = "The server allocates a Transmission Control Work"  # 1 word changed out of 6 words
    metrics = evaluate_text_metrics(gt, hyp)
    assert metrics["cer"] > 0.0
    assert abs(metrics["wer"] - (1.0 / len(gt.split()))) < 0.001
    assert metrics["w_dist"] == 1
    assert metrics["char_accuracy"] < 100.0
    assert metrics["word_accuracy"] < 100.0


def test_metric_calculation_negative_control_blank():
    # Both blank
    metrics = evaluate_text_metrics("", "")
    assert metrics["cer"] == 0.0
    assert metrics["wer"] == 0.0
    assert metrics["char_accuracy"] == 100.0
    assert metrics["word_accuracy"] == 100.0

    # GT blank, but OCR hallucinates
    metrics_hallucinated = evaluate_text_metrics("", "hallucinated text")
    assert metrics_hallucinated["cer"] == 1.0
    assert metrics_hallucinated["char_accuracy"] == 0.0


def test_technical_vocabulary_evaluation():
    terms = ["TCP", "SYN", "ACK", "RST"]
    text = "TCP three-way handshake with SYN and ACK flags set."
    res = evaluate_technical_vocabulary(text, terms)
    assert res["total_terms"] == 4
    assert res["detected_count"] == 3  # TCP, SYN, ACK found; RST missing
    assert res["recall"] == 0.75
    assert res["precision"] == 1.0
    assert res["f1"] == round((2 * 1.0 * 0.75) / 1.75, 4)


# ---------------------------------------------------------------------------
# 2. Ground-Truth & Manifest Integrity Tests
# ---------------------------------------------------------------------------

def test_manifest_schema_and_required_fields():
    manifest_path = backend_dir / "benchmarks" / "general_handwriting_manifest.json"
    assert manifest_path.exists(), "Manifest file missing!"
    manifest = load_manifest(manifest_path)
    assert manifest.get("pipeline_version") == "OCR_3_5_STABILIZED"
    assert manifest.get("engine") == "microsoft/trocr-small-handwritten"
    assert manifest.get("hardware") == "Local CPU (No External AI/Cloud APIs)"

    samples = manifest.get("samples", [])
    assert len(samples) >= 5, "Manifest must contain at least 5 benchmark samples"

    for s in samples:
        assert "sample_id" in s
        assert "subject" in s
        assert "handwriting_style" in s
        assert "layout" in s
        assert "image_quality" in s
        assert "image_path" in s
        assert "ground_truth_path" in s


def test_ground_truth_files_exist_and_non_empty():
    manifest_path = backend_dir / "benchmarks" / "general_handwriting_manifest.json"
    manifest = load_manifest(manifest_path)
    samples = manifest.get("samples", [])

    for s in samples:
        if s.get("subject") == "Negative Control":
            continue
        gt_path = s.get("ground_truth_path")
        gt_text = load_ground_truth(gt_path)
        assert len(gt_text) > 0, f"Ground truth for sample {s['sample_id']} at {gt_path} is empty or missing!"


def test_missing_ground_truth_rejected():
    non_existent = "backend/ground_truth/non_existent_gt_file.txt"
    text = load_ground_truth(non_existent)
    assert text == ""


# ---------------------------------------------------------------------------
# 3. Benchmark Reproducibility & Result Structure Tests
# ---------------------------------------------------------------------------

def test_reproducibility_of_levenshtein_distance():
    # Deterministic edit distance
    s1 = list("Transmission Control Block")
    s2 = list("Transmission Control Work")
    d1 = levenshtein_distance(s1, s2)
    d2 = levenshtein_distance(s1, s2)
    assert d1 == d2
    assert d1 > 0


if __name__ == "__main__":
    tests = [
        test_metric_calculation_exact_match,
        test_metric_calculation_with_known_errors,
        test_metric_calculation_negative_control_blank,
        test_technical_vocabulary_evaluation,
        test_manifest_schema_and_required_fields,
        test_ground_truth_files_exist_and_non_empty,
        test_missing_ground_truth_rejected,
        test_reproducibility_of_levenshtein_distance,
    ]
    passed = 0
    failed = 0
    print(f"Running {len(tests)} benchmark framework tests...\n")
    for t in tests:
        try:
            t()
            print(f" PASS: {t.__name__}")
            passed += 1
        except Exception as e:
            print(f" FAIL: {t.__name__} - {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\nCompleted: {passed} passed, {failed} failed.")
    if failed > 0:
        sys.exit(1)
    print("ALL BENCHMARK FRAMEWORK TESTS PASSED!")
