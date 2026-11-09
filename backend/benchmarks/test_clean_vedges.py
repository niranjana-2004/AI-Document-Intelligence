import cv2
import numpy as np

img = cv2.imread("backend/uploads/handwritten/13/processed/page_001.png")
h, w = img.shape[:2]
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
blur = cv2.GaussianBlur(gray, (5, 5), 0)
_, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

# 1. Detect and suppress margin lines (vertical lines > 100px near edges)
k_v_margin = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 100))
v_margin = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, k_v_margin)
margin_mask = np.zeros_like(thresh)
margin_mask[:, :int(w * 0.15)] = v_margin[:, :int(w * 0.15)]
margin_mask[:, int(w * 0.90):] = v_margin[:, int(w * 0.90):]
clean_thresh = cv2.subtract(thresh, cv2.dilate(margin_mask, np.ones((5, 5), np.uint8)))

# 2. Detect and suppress horizontal notebook ruling lines (> 40% width)
k_ruling = cv2.getStructuringElement(cv2.MORPH_RECT, (int(w * 0.35), 1))
ruling = cv2.morphologyEx(clean_thresh, cv2.MORPH_OPEN, k_ruling)
clean_thresh = cv2.subtract(clean_thresh, ruling)

# 3. Detect structural lines inside page body
k_h = cv2.getStructuringElement(cv2.MORPH_RECT, (max(40, int(w * 0.05)), 2))
h_edges = cv2.morphologyEx(clean_thresh, cv2.MORPH_OPEN, k_h)

k_v = cv2.getStructuringElement(cv2.MORPH_RECT, (2, max(30, int(h * 0.025))))
v_edges = cv2.morphologyEx(clean_thresh, cv2.MORPH_OPEN, k_v)

# Check what structural edges exist
h_ink_total = np.sum(h_edges > 0)
v_ink_total = np.sum(v_edges > 0)
print(f"H_edges ink: {h_ink_total}, V_edges ink: {v_ink_total}")

# Let's inspect rows with high vertical edge ink
v_row_ink = np.sum(v_edges > 0, axis=1)
y_with_v = np.where(v_row_ink > 5)[0]
if len(y_with_v) > 0:
    print(f"V-edges exist at y={y_with_v[0]}..{y_with_v[-1]}")
    # Print distinct clusters of y
    clusters = []
    start = y_with_v[0]
    prev = y_with_v[0]
    for y in y_with_v[1:]:
        if y - prev > 30:
            clusters.append((start, prev))
            start = y
        prev = y
    clusters.append((start, prev))
    print("V-edge clusters:")
    for c in clusters:
        print(f"  Cluster y={c[0]}..{c[1]} (height: {c[1]-c[0]}px, ink: {np.sum(v_edges[c[0]:c[1], :] > 0)})")

