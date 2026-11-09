import cv2
import numpy as np

img = cv2.imread("backend/uploads/handwritten/13/processed/page_001.png")
h, w = img.shape[:2]
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
_, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

# Exactly as in line_segmenter.py:
line_len = max(30, int(w * 0.15))
kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (line_len, 1))
ruling_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_h)
text_thresh = cv2.subtract(thresh, ruling_lines)

print(f"Total thresh ink: {np.sum(thresh > 0)}")
print(f"Ruling lines ink: {np.sum(ruling_lines > 0)}")
print(f"Text thresh ink: {np.sum(text_thresh > 0)}")

# Now check what structural lines remain in text_thresh:
k_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
v_lines = cv2.morphologyEx(text_thresh, cv2.MORPH_OPEN, k_v)
print(f"V-lines ink in upper half: {np.sum(v_lines[:950, :] > 0)}")
print(f"V-lines ink in lower half: {np.sum(v_lines[950:, :] > 0)}")

