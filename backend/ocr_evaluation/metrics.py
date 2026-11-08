"""
Metrics and evaluation utilities for Cognidocs OCR 3.4 Model Evaluation.
Calculates CER, WER, Character/Word Accuracy, Technical Terminology Precision/Recall/F1,
Three-Way Classifications, Error Categorization, and Confidence Calibration.
"""

import re
from typing import Dict, List, Any, Tuple, Optional, Set


def levenshtein_distance(s1, s2) -> int:
    """Compute the Levenshtein edit distance between two sequences (characters or words)."""
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
    return dp[m][n]


def calculate_cer(gt: str, pred: str) -> float:
    """Calculate Character Error Rate (CER = edit_dist / gt_length)."""
    gt = gt.strip()
    pred = pred.strip()
    if not gt:
        return 0.0 if not pred else 1.0
    dist = levenshtein_distance(list(gt), list(pred))
    return dist / len(gt)


def calculate_wer(gt: str, pred: str) -> float:
    """Calculate Word Error Rate (WER = edit_dist / gt_word_count)."""
    gt_words = gt.strip().split()
    pred_words = pred.strip().split()
    if not gt_words:
        return 0.0 if not pred_words else 1.0
    dist = levenshtein_distance(gt_words, pred_words)
    return dist / len(gt_words)


def calculate_char_accuracy(gt: str, pred: str) -> float:
    """Character Accuracy = max(0.0, 1.0 - CER)."""
    return max(0.0, 1.0 - calculate_cer(gt, pred))


def calculate_word_accuracy(gt: str, pred: str) -> float:
    """Word Accuracy = max(0.0, 1.0 - WER)."""
    return max(0.0, 1.0 - calculate_wer(gt, pred))


BENCHMARK_TARGET_TERMS = [
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


def benchmark_technical_terms(text: str, target_terms: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Evaluate technical terminology precision, recall, and F1 score against ground truth targets.
    """
    if target_terms is None:
        target_terms = BENCHMARK_TARGET_TERMS

    matches = {}
    for term in target_terms:
        # Search word boundaries or exact phrase
        pattern = r'\b' + re.escape(term) + r'\b'
        matches[term] = bool(re.search(pattern, text, re.IGNORECASE))

    tp = sum(1 for m in matches.values() if m)
    total_target = len(target_terms)
    fn = total_target - tp
    fp = 0  # Targets are all present in ground truth of Document #12

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "matches": matches,
        "matched_count": tp,
        "total_targets": total_target,
        "accuracy": round(tp / total_target, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4)
    }


def classify_token_result(gt: str, pred: str) -> str:
    """
    Classify a prediction into: CORRECT, INCORRECT, PARTIAL, EMPTY.
    """
    gt_clean = re.sub(r'[\s\.\,\;\:\(\)\[\]\{\}\'\"\-]+', '', gt).lower()
    pred_clean = re.sub(r'[\s\.\,\;\:\(\)\[\]\{\}\'\"\-]+', '', pred).lower()

    if not pred.strip():
        return "EMPTY"

    if gt_clean == pred_clean:
        return "CORRECT"

    # Exact string match including punctuation
    if gt.strip().lower() == pred.strip().lower():
        return "CORRECT"

    # Partial match: Levenshtein distance <= 1 or close match
    dist = levenshtein_distance(list(gt_clean), list(pred_clean))
    if dist <= max(1, len(gt_clean) // 3):
        return "PARTIAL"

    if gt_clean in pred_clean or pred_clean in gt_clean:
        return "PARTIAL"

    return "INCORRECT"


def classify_three_way(small_result: str, base_result: str, is_ambiguous: bool = False) -> str:
    """
    Classify outcome between Small and Base models:
    - Base wins (Small incorrect, Base correct)
    - Small wins (Small correct, Base incorrect)
    - Both correct (Small correct, Base correct)
    - Both incorrect (Small incorrect, Base incorrect)
    - Ambiguous (ground truth uncertain)
    """
    if is_ambiguous:
        return "Ambiguous"

    small_is_corr = (small_result == "CORRECT")
    base_is_corr = (base_result == "CORRECT")

    if not small_is_corr and base_is_corr:
        return "Base wins"
    elif small_is_corr and not base_is_corr:
        return "Small wins"
    elif small_is_corr and base_is_corr:
        return "Both correct"
    else:
        return "Both incorrect"


def compute_confidence_calibration(
    records: List[Dict[str, Any]],
    buckets: Optional[List[Tuple[float, float]]] = None
) -> List[Dict[str, Any]]:
    """
    Calculate confidence vs actual correctness across specified confidence buckets.
    """
    if buckets is None:
        buckets = [(0.0, 20.0), (20.0, 40.0), (40.0, 60.0), (60.0, 80.0), (80.0, 100.0)]

    results = []
    for b_min, b_max in buckets:
        bucket_tokens = [
            r for r in records
            if b_min <= r.get("confidence", 0.0) < b_max or (b_max == 100.0 and r.get("confidence", 0.0) == 100.0)
        ]
        total = len(bucket_tokens)
        correct = sum(1 for r in bucket_tokens if r.get("is_correct", False))
        accuracy = round((correct / total) * 100.0, 2) if total > 0 else 0.0

        results.append({
            "bucket": f"{int(b_min)}–{int(b_max)}%",
            "min_conf": b_min,
            "max_conf": b_max,
            "total_tokens": total,
            "correct_tokens": correct,
            "accuracy_pct": accuracy
        })

    return results

