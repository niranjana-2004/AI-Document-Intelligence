"""
Error inspection script for Document #12 to analyze the exact nature of remaining OCR errors.
"""
import os
import sys
import difflib
import json
import re

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from create_ground_truth import GROUND_TRUTH_PAGES
from app.core.database import SessionLocal
from app.models.handwritten_page import HandwrittenPage
from benchmark_ocr import levenshtein_distance

db = SessionLocal()
pages = db.query(HandwrittenPage).filter(HandwrittenPage.document_id == 12).order_by(HandwrittenPage.page_number).all()

print("=" * 60)
print("DETAILED ERROR ANALYSIS ACROSS DOCUMENT #12")
print("=" * 60)

for p in pages:
    gt_text = GROUND_TRUTH_PAGES[p.page_number].strip()
    rec_text = (p.edited_transcription or "").strip()
    raw_text = (p.raw_transcription or "").strip()

    gt_words = gt_text.split()
    rec_words = rec_text.split()

    matcher = difflib.SequenceMatcher(None, gt_words, rec_words)
    opcodes = matcher.get_opcodes()

    print(f"\n--- PAGE {p.page_number} ---")
    diff_count = 0
    for tag, i1, i2, j1, j2 in opcodes:
        if tag != 'equal':
            gt_chunk = " ".join(gt_words[i1:i2])
            rec_chunk = " ".join(rec_words[j1:j2])
            print(f"[{tag.upper():7s}] GT:  '{gt_chunk}'\n          REC: '{rec_chunk}'")
            diff_count += 1
            if diff_count >= 15:
                print("  ... (truncated further page diffs)")
                break

db.close()

