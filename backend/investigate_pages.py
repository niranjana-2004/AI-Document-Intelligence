import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

from app.services.handwriting.image_preprocessor import read_image_safe
from app.services.handwriting.line_segmenter import segment_page_into_lines
from app.services.handwriting.ocr_service import recognize_line_image, get_ocr_engine

def investigate():
    doc_dir = Path("uploads/handwritten/12")
    orig_dir = doc_dir / "original"
    proc_dir = doc_dir / "processed"
    
    # Check crops on page 1
    p1_orig = orig_dir / "page_001.png"
    p1_proc = proc_dir / "page_001.png"
    
    print(f"P1 Orig exists: {p1_orig.exists()}, Proc exists: {p1_proc.exists()}")
    
    img_orig = read_image_safe(p1_orig)
    img_proc = read_image_safe(p1_proc)
    
    print(f"Orig shape: {img_orig.shape}, Proc shape: {img_proc.shape}")
    
    lines_orig, empty_orig = segment_page_into_lines(img_orig)
    print(f"Lines from Orig: {len(lines_orig)}, empty: {empty_orig}")
    for idx, l in enumerate(lines_orig):
        print(f"  Line {idx+1}: bbox={l.bbox}")
        
    lines_proc, empty_proc = segment_page_into_lines(img_proc)
    print(f"Lines from Proc: {len(lines_proc)}, empty: {empty_proc}")
    for idx, l in enumerate(lines_proc):
        print(f"  Line {idx+1}: bbox={l.bbox}")

    # Run OCR on lines of page 1
    print("\n--- RUNNING OCR ON PAGE 1 LINES ---")
    for idx, l in enumerate(lines_orig):
        # crop from orig and proc
        x, y, w, h = l.bbox
        crop_orig = Image.fromarray(cv2.cvtColor(img_orig[y:y+h, x:x+w], cv2.COLOR_BGR2RGB))
        crop_proc = Image.fromarray(cv2.cvtColor(img_proc[y:y+h, x:x+w], cv2.COLOR_BGR2RGB))
        
        res_orig = recognize_line_image(crop_orig)
        res_proc = recognize_line_image(crop_proc)
        
        print(f"Line {idx+1} (bbox {l.bbox}):")
        print(f"   [ORIG CROP] text: '{res_orig.get('text')}' (conf: {res_orig.get('confidence')}%)")
        print(f"   [PROC CROP] text: '{res_proc.get('text')}' (conf: {res_proc.get('confidence')}%)")

if __name__ == "__main__":
    investigate()
