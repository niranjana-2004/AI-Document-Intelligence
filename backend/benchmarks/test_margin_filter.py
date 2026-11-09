import cv2
import numpy as np

img = cv2.imread("backend/uploads/handwritten/13/processed/page_001.png")
h, w = img.shape[:2]
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
blur = cv2.GaussianBlur(gray, (5, 5), 0)
_, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

# Filter out margin borders: left margin (x < 0.12*w) and right edge (x > 0.92*w)
# Also top edge (y < 0.02*h) and bottom edge (y > 0.98*h)
inner_thresh = thresh.copy()
inner_thresh[:, :int(w * 0.12)] = 0
inner_thresh[:, int(w * 0.92):] = 0
inner_thresh[:int(h * 0.02), :] = 0
inner_thresh[int(h * 0.98):, :] = 0

# Ruling line suppression (thin horizontal lines spanning > 50% inner width)
inner_w = int(w * 0.80)
k_ruling = cv2.getStructuringElement(cv2.MORPH_RECT, (int(inner_w * 0.5), 1))
ruling = cv2.morphologyEx(inner_thresh, cv2.MORPH_OPEN, k_ruling)
inner_thresh = cv2.subtract(inner_thresh, ruling)

# Find structural lines
k_h = cv2.getStructuringElement(cv2.MORPH_RECT, (max(35, int(w * 0.04)), 2))
h_edges = cv2.morphologyEx(inner_thresh, cv2.MORPH_OPEN, k_h)

k_v = cv2.getStructuringElement(cv2.MORPH_RECT, (2, max(25, int(h * 0.02))))
v_edges = cv2.morphologyEx(inner_thresh, cv2.MORPH_OPEN, k_v)

box_edges = cv2.add(h_edges, v_edges)
k_close = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
closed = cv2.morphologyEx(box_edges, cv2.MORPH_CLOSE, k_close)

cnts, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
print(f"Detected {len(cnts)} candidate contours:")
for c in cnts:
    x, y, bw, bh = cv2.boundingRect(c)
    if bw > 60 and bh > 25:
        sub_h = h_edges[y:y+bh, x:x+bw]
        sub_v = v_edges[y:y+bh, x:x+bw]
        h_cnt = np.sum(sub_h > 0)
        v_cnt = np.sum(sub_v > 0)
        print(f"  Contour bbox=[x={x}, y={y}, w={bw}, h={bh}], H_ink={h_cnt}, V_ink={v_cnt}")

