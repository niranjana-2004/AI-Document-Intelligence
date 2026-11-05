import os
import sys
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

from app.services.handwriting.ocr_service import recognize_line_image
from benchmark_ocr import calculate_cer

def test_preprocessing_comparison():
    # Page 1 paths
    orig_path = Path("uploads/handwritten/12/original/page_001.png")
    proc_path = Path("uploads/handwritten/12/processed/page_001.png")

    if not orig_path.exists() or not proc_path.exists():
        print("Page 1 images not found!")
        return

    orig_bgr = cv2.imread(str(orig_path))
    proc_bgr = cv2.imread(str(proc_path))

    # Sample line: Line 1 "Niranjana A S 21BIT042 Notes on" and Line 2 "TCP Attacks 1. TCP SYN Flood"
    # In processed image (approx 1800x2400)
    # Let's crop sample bounding box around line 2:
    # y: 150 to 220, x: 200 to 1600
    h_proc, w_proc = proc_bgr.shape[:2]
    h_orig, w_orig = orig_bgr.shape[:2]

    # Let's test 3 crops:
    # Line A: Title line "Niranjana A S 21BIT042 Notes on"
    # Line B: "TCP Attacks 1. TCP SYN Flood"
    # Line C: "attack that exploits the TCP three-way"
    
    # Let's use the actual bounding boxes saved in evaluate_results.json
    import json
    with open("evaluate_results.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    p1_lines = data["pages"][0]["raw_lines"]
    # We also have the bboxes in the DB
    from app.core.database import SessionLocal
    from app.models.handwritten_page import HandwrittenPage
    db = SessionLocal()
    page1 = db.query(HandwrittenPage).filter(HandwrittenPage.document_id == 12, HandwrittenPage.page_number == 1).first()
    meta_lines = page1.ocr_metadata.get("lines", [])[:3]
    db.close()

    print("================ PREPROCESSING COMPARISON (SAMPLE LINES) ================")
    for idx, line_info in enumerate(meta_lines):
        bbox = line_info["bbox"]
        bx, by, bw, bh = bbox
        
        # Crop 1: Processed image crop
        crop_proc = proc_bgr[max(0, by):min(h_proc, by+bh), max(0, bx):min(w_proc, bx+bw)]
        pil_proc = Image.fromarray(cv2.cvtColor(crop_proc, cv2.COLOR_BGR2RGB))
        res_proc = recognize_line_image(pil_proc)

        # Crop 2: Original image crop (scaled coordinates if dimensions differ)
        sy = h_orig / h_proc
        sx = w_orig / w_proc
        obx, oby, obw, obh = int(bx*sx), int(by*sy), int(bw*sx), int(bh*sy)
        crop_orig = orig_bgr[max(0, oby):min(h_orig, oby+obh), max(0, obx):min(w_orig, obx+obw)]
        pil_orig = Image.fromarray(cv2.cvtColor(crop_orig, cv2.COLOR_BGR2RGB))
        res_orig = recognize_line_image(pil_orig)

        # Crop 3: Clean crop with morphological ruling lines removed
        gray_proc = cv2.cvtColor(crop_proc, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray_proc, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        k_len = max(15, int(crop_proc.shape[1] * 0.15))
        ruling = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (k_len, 1)))
        no_ruling_thresh = cv2.bitwise_and(thresh, cv2.bitwise_not(ruling))
        clean_line_bgr = cv2.cvtColor(cv2.bitwise_not(no_ruling_thresh), cv2.COLOR_GRAY2BGR)
        pil_clean = Image.fromarray(cv2.cvtColor(clean_line_bgr, cv2.COLOR_BGR2RGB))
        res_clean = recognize_line_image(pil_clean)

        print(f"\nLine {idx+1} BBox {bbox}:")
        print(f"  * Current Processed Crop : '{res_proc.get('text')}' (conf: {res_proc.get('confidence')}%)")
        print(f"  * Original Raw Crop      : '{res_orig.get('text')}' (conf: {res_orig.get('confidence')}%)")
        print(f"  * Ruling Lines Subtracted: '{res_clean.get('text')}' (conf: {res_clean.get('confidence')}%)")

if __name__ == "__main__":
    test_preprocessing_comparison()

