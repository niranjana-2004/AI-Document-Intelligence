import cv2
import numpy as np

img = cv2.imread("backend/uploads/handwritten/13/processed/page_001.png")
h, w = img.shape[:2]
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
blur = cv2.GaussianBlur(gray, (5, 5), 0)
_, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

# Connected components border clearing
num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(thresh)
border_mask = np.zeros_like(thresh)
for i in range(1, num_labels):
    bx = stats[i, cv2.CC_STAT_LEFT]
    by = stats[i, cv2.CC_STAT_TOP]
    bw = stats[i, cv2.CC_STAT_WIDTH]
    bh = stats[i, cv2.CC_STAT_HEIGHT]
    area = stats[i, cv2.CC_STAT_AREA]

    # If it touches the outer 5px border and is either very wide or very tall
    touches_border = (bx <= 4 or by <= 4 or (bx + bw) >= w - 4 or (by + bh) >= h - 4)
    if touches_border and (bw > w * 0.5 or bh > h * 0.3):
        border_mask[labels == i] = 255

clean = cv2.subtract(thresh, border_mask)
print(f"Cleared border pixels: {np.sum(border_mask > 0)}")

# Check vertical lines now
k_v = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 35))
v_lines = cv2.morphologyEx(clean, cv2.MORPH_OPEN, k_v)
cnts, _ = cv2.findContours(v_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
print(f"Remaining vertical lines: {len(cnts)}")
for c in cnts:
    bx, by, bw, bh = cv2.boundingRect(c)
    if bh > 40:
        print(f"  V-line at x={bx}..{bx+bw}, y={by}..{by+bh}, h={bh}")

