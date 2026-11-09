import sys
from pathlib import Path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

import cv2
import numpy as np
from app.services.handwriting.layout_intelligence_service import _clean_scanner_frame_and_ruling_lines, _detect_diagram_boxes

img = cv2.imread("backend/uploads/handwritten/13/processed/page_001.png")
h, w = img.shape[:2]
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
blur = cv2.GaussianBlur(gray, (5, 5), 0)
_, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

clean_full, clean_text = _clean_scanner_frame_and_ruling_lines(thresh, w, h)
boxes = _detect_diagram_boxes(clean_full, w, h)
print(f"Total boxes in Doc 13: {len(boxes)}")
for b in boxes:
    print(f"  Box: {b['bbox']} (top={b['top_len']}, bot={b['bot_len']}, left={b['left_len']}, right={b['right_len']})")
