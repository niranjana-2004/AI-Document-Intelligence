"""
Unit and Adversarial Test Suite for Cognidocs OCR 3.5:
Context-Aware Word & Phrase Recovery

Covers:
1. Word-boundary analysis (adaptive scale, whitespace dips, split/merge evidence)
2. Compound & hyphenated phrase recovery ('handshake', 'three-way', 'denial-of-service')
3. Cursive stroke character confusion and candidate ranking
4. Safety Gate & Common-word protection guardrails (zero hallucination, no false mutation)
5. DocumentConsistencyIndex (cross-page vocabulary & bigrams)
6. Integration test via recover_technical_line
"""

import numpy as np
import cv2

from app.services.handwriting.boundary_analyzer import (
    estimate_line_spacing_statistics,
    find_ink_valleys_in_token,
    evaluate_split_boundary_evidence,
    evaluate_merge_boundary_evidence
)
from app.services.handwriting.candidate_ranker import (
    WordCandidate,
    score_candidate,
    rank_candidates_for_token
)
from app.services.handwriting.word_context_recovery_service import (
    DocumentConsistencyIndex,
    score_local_context,
    generate_word_boundary_splits,
    generate_character_alternatives,
    CURSIVE_STROKE_PAIRS
)
from app.services.handwriting.phrase_recovery_service import (
    recover_phrases_in_line,
    COMPOUND_MERGES,
    HYPHENATED_COMPOUNDS
)
from app.services.handwriting.technical_recovery_service import recover_technical_line
from app.services.handwriting.terminology_service import extract_document_terminology


# ---------------------------------------------------------------------------
# 1. Boundary Analyzer Tests
# ---------------------------------------------------------------------------

def test_estimate_line_spacing_statistics():
    # Create synthetic line image with text-like alternating dark and light stripes
    img = np.ones((40, 400, 3), dtype=np.uint8) * 255
    # Draw 5 simulated word blocks
    for start in [30, 110, 190, 270, 350]:
        img[10:30, start:start+50] = 0

    tokens = [
        {"token_text": "word1", "local_bbox": [30, 10, 50, 20]},
        {"token_text": "word2", "local_bbox": [110, 10, 50, 20]},
        {"token_text": "word3", "local_bbox": [190, 10, 50, 20]},
        {"token_text": "word4", "local_bbox": [270, 10, 50, 20]},
        {"token_text": "word5", "local_bbox": [350, 10, 50, 20]},
    ]

    stats = estimate_line_spacing_statistics(img, tokens)
    assert stats["line_height"] == 40.0
    assert stats["median_gap"] == 30.0  # 110 - (30+50) = 30
    assert stats["mean_char_w"] > 0.0


def test_find_ink_valleys_in_token():
    # Synthetic token image with two characters separated by a white valley in the middle
    token_img = np.ones((30, 80, 3), dtype=np.uint8) * 255
    token_img[5:25, 10:35] = 0   # Left char
    # Valley from 35 to 45 (10px wide)
    token_img[5:25, 45:70] = 0   # Right char

    valleys = find_ink_valleys_in_token(token_img, min_valley_width=3)
    assert len(valleys) >= 1
    v = valleys[0]
    assert 35 <= v["col"] <= 45
    assert v["width"] >= 5


def test_evaluate_split_boundary_evidence():
    token_img = np.ones((30, 80, 3), dtype=np.uint8) * 255
    token_img[5:25, 10:35] = 0
    token_img[5:25, 45:70] = 0

    line_scale = {"mean_char_w": 12.0, "median_gap": 15.0}
    # Split between 4 chars total: split at index 2 (50% across token)
    ev = evaluate_split_boundary_evidence(token_img, split_char_index=2, total_token_chars=4, line_scale=line_scale)
    assert ev["has_visual_gap"] is True
    assert ev["boundary_score"] >= 0.70


def test_evaluate_merge_boundary_evidence():
    line_scale = {"median_gap": 20.0, "mean_char_w": 15.0}
    # Very narrow gap (4px vs 20px median) -> strong merge evidence
    box1 = [10, 5, 40, 25]
    box2 = [54, 5, 40, 25]  # gap = 4px
    ev = evaluate_merge_boundary_evidence(box1, box2, line_scale)
    assert ev["has_narrow_gap"] is True
    assert ev["boundary_score"] >= 0.80

    # Wide normal gap (25px vs 20px median) -> does not support merge
    box3 = [100, 5, 40, 25]
    ev_wide = evaluate_merge_boundary_evidence(box1, box3, line_scale)
    assert ev_wide["has_narrow_gap"] is False
    assert ev_wide["boundary_score"] < 0.50


# ---------------------------------------------------------------------------
# 2. Phrase and Compound Recovery Tests
# ---------------------------------------------------------------------------

def test_recover_compound_merge():
    # 'hand' and 'shake' separated by narrow gap
    line_scale = {"median_gap": 18.0, "mean_char_w": 14.0}
    tokens = [
        {"token_text": "hand", "clean_text": "hand", "token_bbox": [10, 5, 30, 20]},
        {"token_text": "shake", "clean_text": "shake", "token_bbox": [43, 5, 40, 20]}  # 3px gap
    ]
    updated, corrs = recover_phrases_in_line(tokens, None, line_scale)
    assert len(updated) == 1
    assert updated[0]["token_text"] == "handshake"
    assert len(corrs) == 1
    assert corrs[0]["status"] == "accepted"


def test_recover_hyphenated_compound():
    line_scale = {"median_gap": 18.0, "mean_char_w": 14.0}
    tokens = [
        {"token_text": "three", "clean_text": "three", "token_bbox": [10, 5, 35, 20]},
        {"token_text": "way", "clean_text": "way", "token_bbox": [55, 5, 25, 20]}
    ]
    updated, corrs = recover_phrases_in_line(tokens, None, line_scale)
    assert len(updated) == 1
    assert updated[0]["token_text"] == "three-way"
    assert len(corrs) == 1
    assert corrs[0]["status"] == "accepted"


def test_recover_triplet_compound():
    line_scale = {"median_gap": 18.0, "mean_char_w": 14.0}
    tokens = [
        {"token_text": "denial", "clean_text": "denial", "token_bbox": [10, 5, 40, 20]},
        {"token_text": "of", "clean_text": "of", "token_bbox": [55, 5, 15, 20]},
        {"token_text": "service", "clean_text": "service", "token_bbox": [75, 5, 50, 20]},
        {"token_text": "attack", "clean_text": "attack", "token_bbox": [130, 5, 45, 20]}
    ]
    updated, corrs = recover_phrases_in_line(tokens, None, line_scale)
    assert len(updated) == 2
    assert updated[0]["clean_text"] == "denial-of-service"
    assert updated[1]["clean_text"] == "attack"
    assert len(corrs) == 1


# ---------------------------------------------------------------------------
# 3. Document Consistency Index & Context Scoring Tests
# ---------------------------------------------------------------------------

def test_document_consistency_index():
    pages_lines = {
        1: ["TCP SYN flood exhausts the server resources", "The TCP connection state"],
        2: ["TCP three-way handshake establishes connection", "attacker sends TCP packets"],
        3: ["TCP RST attack terminates the session"]
    }
    index = DocumentConsistencyIndex(pages_lines)
    assert index.get_document_score("tcp") >= 0.90  # Appears on every page
    assert index.get_document_score("handshake") >= 0.60
    assert index.get_document_score("unseenwordxyz") == 0.30
    assert index.get_bigram_score("three-way", "handshake") >= 0.70


# ---------------------------------------------------------------------------
# 4. Candidate Ranker & Safety Gate Tests
# ---------------------------------------------------------------------------

def test_safety_gate_rejects_hallucination():
    # Visual similarity < 0.55 must be strictly rejected
    hallucinated = WordCandidate(
        word_id="w1",
        page_number=1,
        line_id=1,
        word_index=1,
        original_text="ICCP",
        candidate_text="Wikipedia",
        bounding_box=[10, 10, 40, 20],
        visual_similarity=0.20,
        boundary_confidence=0.50,
        context_score=0.90,
        language_score=0.95,
        technical_score=0.10,
        document_score=0.10,
        source="TEST"
    )
    scored = score_candidate(hallucinated, is_boundary_op=False)
    assert scored.decision == "REJECTED"


def test_safety_gate_protects_valid_common_words():
    # A valid common word like 'the' should NOT be mutated into another word without high threshold
    valid_common = WordCandidate(
        word_id="w2",
        page_number=1,
        line_id=1,
        word_index=1,
        original_text="the",
        candidate_text="tie",
        bounding_box=[10, 10, 30, 20],
        visual_similarity=0.68,
        boundary_confidence=0.70,
        context_score=0.70,
        language_score=0.85,
        technical_score=0.20,
        document_score=0.40,
        source="CHAR_AMBIGUITY"
    )
    scored = score_candidate(valid_common, is_boundary_op=False, is_common_protected=True)
    assert scored.decision == "RAW"  # Protected! Not mutated!


def test_safety_gate_accepts_grounded_recovery():
    # High optical agreement + context agreement -> ACCEPTED
    grounded = WordCandidate(
        word_id="w3",
        page_number=1,
        line_id=1,
        word_index=1,
        original_text="Polls",
        candidate_text="falls",
        bounding_box=[10, 10, 35, 20],
        visual_similarity=0.88,
        boundary_confidence=0.75,
        context_score=0.85,
        language_score=0.92,
        technical_score=0.50,
        document_score=0.80,
        source="CHAR_AMBIGUITY"
    )
    scored = score_candidate(grounded, is_boundary_op=False, is_common_protected=False)
    assert scored.decision == "ACCEPTED"
    assert scored.final_score >= 0.78


# ---------------------------------------------------------------------------
# 5. Integration Test via recover_technical_line
# ---------------------------------------------------------------------------

def test_recover_technical_line_full_integration():
    vocab_index = extract_document_terminology([
        "TCP SYN flood attacks the server",
        "TCP three-way handshake",
        "DoS denial-of-service attack"
    ], subject="Computer Networks")

    # Raw line with technical acronym corruption 'ICCP' and phrase 'three way'
    raw_line = "ICCP three way handshake is vulnerable to SYN flood"

    rec_line, corrs = recover_technical_line(
        raw_line_text=raw_line,
        line_idx=1,
        page_num=1,
        vocab_index=vocab_index,
        line_crop_bgr=None,
        line_conf=68.0
    )

    assert "TCP" in rec_line
    assert "SYN" in rec_line


if __name__ == "__main__":
    tests = [
        test_estimate_line_spacing_statistics,
        test_find_ink_valleys_in_token,
        test_evaluate_split_boundary_evidence,
        test_evaluate_merge_boundary_evidence,
        test_recover_compound_merge,
        test_recover_hyphenated_compound,
        test_recover_triplet_compound,
        test_document_consistency_index,
        test_safety_gate_rejects_hallucination,
        test_safety_gate_protects_valid_common_words,
        test_safety_gate_accepts_grounded_recovery,
        test_recover_technical_line_full_integration
    ]
    passed = 0
    failed = 0
    print(f"Running {len(tests)} OCR 3.5 tests...\n")
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
        exit(1)
    print("ALL OCR 3.5 TESTS PASSED!")
