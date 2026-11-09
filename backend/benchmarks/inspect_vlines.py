import cv2
import numpy as np

img = cv2.imread("backend/uploads/handwritten/13/processed/page_001.png")
h, w = img.shape[:2]
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
_, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

# Find vertical lines
k_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 60))
v_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, k_v)

cnts, _ = cv2.findContours(v_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
print(f"Detected {len(cnts)} vertical line contours:")
for c in cnts:
    x, y, bw, bh = cv2.boundingRect(c)
    if bh > 80:
        print(f"  V-Line at x={x}..{x+bw}, y={y}..{y+bh}, h={bh}")

