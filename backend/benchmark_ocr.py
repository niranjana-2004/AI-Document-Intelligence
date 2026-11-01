import sys
import os
import time
import tracemalloc
from pathlib import Path
from typing import List, Tuple, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.main import app

def levenshtein_distance(seq1: List[Any], seq2: List[Any]) -> int:
    """Standard dynamic programming Levenshtein edit distance."""
    size_x = len(seq1) + 1
    size_y = len(seq2) + 1
    matrix = [[0] * size_y for _ in range(size_x)]
    
    for x in range(size_x):
        matrix[x][0] = x
    for y in range(size_y):
        matrix[0][y] = y

    for x in range(1, size_x):
        for y in range(1, size_y):
            if seq1[x - 1] == seq2[y - 1]:
                matrix[x][y] = matrix[x - 1][y - 1]
            else:
                matrix[x][y] = min(
                    matrix[x - 1][y] + 1,       # deletion
                    matrix[x][y - 1] + 1,       # insertion
                    matrix[x - 1][y - 1] + 1    # substitution
                )
    return matrix[size_x - 1][size_y - 1]

def calculate_cer(ref: str, hyp: str) -> float:
    """Character Error Rate."""
    ref_chars = list(ref)
    hyp_chars = list(hyp)
    if not ref_chars:
        return 0.0 if not hyp_chars else 1.0
    dist = levenshtein_distance(ref_chars, hyp_chars)
    return dist / len(ref_chars)

def calculate_wer(ref: str, hyp: str) -> float:
    """Word Error Rate."""
    ref_words = ref.split()
    hyp_words = hyp.split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    dist = levenshtein_distance(ref_words, hyp_words)
    return dist / len(ref_words)

def run_benchmark(transcriptions_by_page: Dict[int, str], label: str = "BASELINE") -> Dict[str, Any]:
    from create_ground_truth import GROUND_TRUTH_PAGES
    
    print(f"\n=======================================================")
    print(f"      OCR BENCHMARK EVALUATION: {label}")
    print(f"=======================================================")
    
    results = {}
    total_ref_chars = 0
    total_char_dist = 0
    total_ref_words = 0
    total_word_dist = 0
    
    for page_num in range(1, 8):
        gt = GROUND_TRUTH_PAGES.get(page_num, "").strip()
        hyp = transcriptions_by_page.get(page_num, "").strip()
        
        cer = calculate_cer(gt, hyp)
        wer = calculate_wer(gt, hyp)
        
        c_dist = levenshtein_distance(list(gt), list(hyp))
        w_dist = levenshtein_distance(gt.split(), hyp.split())
        
        total_ref_chars += len(gt)
        total_char_dist += c_dist
        total_ref_words += len(gt.split())
        total_word_dist += w_dist
        
        gt_lines = len(gt.splitlines())
        hyp_lines = len(hyp.splitlines())
        
        print(f"Page {page_num}:")
        print(f"  * Lines: Ref={gt_lines}, Hyp={hyp_lines}")
        print(f"  * CER: {cer*100:.2f}% (Edits: {c_dist} / {len(gt)} chars)")
        print(f"  * WER: {wer*100:.2f}% (Edits: {w_dist} / {len(gt.split())} words)")
        print(f"  * Sample GT : {gt[:90]}...")
        print(f"  * Sample Hyp: {hyp[:90]}...\n")
        
        results[page_num] = {
            "cer": cer,
            "wer": wer,
            "char_edits": c_dist,
            "word_edits": w_dist,
            "ref_chars": len(gt),
            "ref_words": len(gt.split()),
            "hyp_lines": hyp_lines
        }
        
    avg_cer = (total_char_dist / total_ref_chars) if total_ref_chars > 0 else 0
    avg_wer = (total_word_dist / total_ref_words) if total_ref_words > 0 else 0
    
    print(f"--- OVERALL SUMMARY ({label}) ---")
    print(f"Overall CER: {avg_cer*100:.2f}%")
    print(f"Overall WER: {avg_wer*100:.2f}%")
    print(f"Total Reference Characters: {total_ref_chars}")
    print(f"Total Reference Words     : {total_ref_words}")
    print(f"=======================================================\n")
    
    return {
        "page_results": results,
        "overall_cer": avg_cer,
        "overall_wer": avg_wer,
        "total_chars": total_ref_chars,
        "total_words": total_ref_words
    }

if __name__ == "__main__":
    from app.core.database import SessionLocal
    from app.models.handwritten_page import HandwrittenPage
    
    db = SessionLocal()
    try:
        pages = db.query(HandwrittenPage).filter(HandwrittenPage.document_id == 12).order_by(HandwrittenPage.page_number).all()
        baseline_trans = {}
        for p in pages:
            baseline_trans[p.page_number] = p.edited_transcription or p.raw_transcription or ""
        run_benchmark(baseline_trans, label="CURRENT DATABASE BASELINE (DOC #12)")
    finally:
        db.close()

