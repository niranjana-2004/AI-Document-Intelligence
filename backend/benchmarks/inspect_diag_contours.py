import sys
from pathlib import Path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

import cv2
import numpy as np
from app.services.handwriting.layout_intelligence_service import _clean_scanner_frame_and_ruling_lines

img = cv2.imread("backend/uploads/handwritten/13/processed/page_001.png")
h, w = img.shape[:2]
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
blur = cv2.GaussianBlur(gray, (5, 5), 0)
_, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

clean_full, clean_text = _clean_scanner_frame_and_ruling_lines(thresh, w, h)

# Crop y=950..1800
diag_thresh = clean_full[950:1800, :]

# Find contours in diagram region
cnts, _ = cv2.findContours(diag_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
print(f"Contours in y=950..1800: {len(cnts)}")
for c in cnts:
    bx, by, bw, bh = cv2.boundingRect(c)
    if bw > 100 and bh > 30:
        print(f"  Contour bbox=[x={bx}, y={by+950}, w={bw}, h={bh}]")

