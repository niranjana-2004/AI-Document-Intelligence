import cv2
import numpy as np

img = cv2.imread("backend/uploads/handwritten/13/processed/page_001.png")
h, w = img.shape[:2]
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
_, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

k_v = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 30))
v_edges = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, k_v)

sub_v = v_edges[291:1087, :]
col_sums = np.sum(sub_v > 0, axis=0)
active_cols = np.where(col_sums > 50)[0]
print("Active columns in y=291..1087:", active_cols)

