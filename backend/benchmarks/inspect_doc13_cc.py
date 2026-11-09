import cv2
import numpy as np
from pathlib import Path

img = cv2.imread("backend/benchmarks/artifacts/layout_40_visualizations/doc13_bottom_half.png")
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
blur = cv2.GaussianBlur(gray, (5, 5), 0)
_, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

# Connected components with stats
num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(thresh)
print(f"Connected components count: {num_labels}")

# Sort by area descending
sorted_indices = np.argsort(stats[:, cv2.CC_STAT_AREA])[::-1]
for idx in sorted_indices[1:25]:  # skip background
    x = stats[idx, cv2.CC_STAT_LEFT]
    y = stats[idx, cv2.CC_STAT_TOP]
    w = stats[idx, cv2.CC_STAT_WIDTH]
    h = stats[idx, cv2.CC_STAT_HEIGHT]
    area = stats[idx, cv2.CC_STAT_AREA]
    print(f"CC {idx}: bbox=[x={x}, y={y+950}, w={w}, h={h}], area={area}, density={area/(w*h):.2f}")

