import cv2
import numpy as np

img = cv2.imread("backend/uploads/handwritten/13/processed/page_001.png")
h, w = img.shape[:2]
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
blur = cv2.GaussianBlur(gray, (5, 5), 0)
_, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

# Suppress scan borders (within 15px of any image edge)
border_mask = np.zeros_like(thresh)
border_mask[:15, :] = 255
border_mask[-15:, :] = 255
border_mask[:, :15] = 255
border_mask[:, -15:] = 255
clean_thresh = cv2.subtract(thresh, border_mask)

# Ruling lines (> 40% width)
k_ruling = cv2.getStructuringElement(cv2.MORPH_RECT, (int(w * 0.40), 1))
ruling = cv2.morphologyEx(clean_thresh, cv2.MORPH_OPEN, k_ruling)
clean_thresh = cv2.subtract(clean_thresh, ruling)

# Structural lines
k_h = cv2.getStructuringElement(cv2.MORPH_RECT, (max(50, int(w * 0.05)), 2))
h_lines = cv2.morphologyEx(clean_thresh, cv2.MORPH_OPEN, k_h)

k_v = cv2.getStructuringElement(cv2.MORPH_RECT, (2, max(40, int(h * 0.025))))
v_lines = cv2.morphologyEx(clean_thresh, cv2.MORPH_OPEN, k_v)

combined_lines = cv2.add(h_lines, v_lines)
k_close = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
closed = cv2.morphologyEx(combined_lines, cv2.MORPH_CLOSE, k_close)

cnts, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
print(f"Detected {len(cnts)} contours:")
for c in cnts:
    x, y, bw, bh = cv2.boundingRect(c)
    if bw > 80 and bh > 35:
        # Check border support
        sub_h = h_lines[y:y+bh, x:x+bw]
        sub_v = v_lines[y:y+bh, x:x+bw]
        h_pix = np.sum(sub_h > 0)
        v_pix = np.sum(sub_v > 0)
        if h_pix > 50 and v_pix > 35:
            print(f"  Box: y={y}..{y+bh}, x={x}..{x+bw}, bw={bw}, bh={bh}")

