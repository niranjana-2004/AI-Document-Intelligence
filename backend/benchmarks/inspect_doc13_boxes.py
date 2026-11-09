import cv2
import numpy as np
from pathlib import Path

img_path = Path("backend/uploads/handwritten/13/processed/page_001.png")
if not img_path.exists():
    img_path = Path("uploads/handwritten/13/processed/page_001.png")

img = cv2.imread(str(img_path))
h, w = img.shape[:2]

# Crop top half and bottom half
top_half = img[0:950, :]
bottom_half = img[950:, :]

# Save crops for visual debugging
out_dir = Path("backend/benchmarks/artifacts/layout_40_visualizations")
out_dir.mkdir(parents=True, exist_ok=True)
cv2.imwrite(str(out_dir / "doc13_top_half.png"), top_half)
cv2.imwrite(str(out_dir / "doc13_bottom_half.png"), bottom_half)

# Analyze bottom half for boxes and arrows
gray_bottom = cv2.cvtColor(bottom_half, cv2.COLOR_BGR2GRAY)
blur = cv2.GaussianBlur(gray_bottom, (5, 5), 0)
_, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

# Find large rectangular contours
contours, hierarchy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
print(f"Total contours in bottom half: {len(contours)}")

boxes = []
for c in contours:
    x, y, bw, bh = cv2.boundingRect(c)
    area = cv2.contourArea(c)
    # Check if rectangular contour
    peri = cv2.arcLength(c, True)
    approx = cv2.approxPolyDP(c, 0.03 * peri, True)
    if bw > 150 and bh > 60:
        boxes.append((x, y + 950, bw, bh, area, len(approx)))

print(f"Detected {len(boxes)} large candidate boxes:")
for b in boxes:
    print(f"Box: bbox=[x={b[0]}, y={b[1]}, w={b[2]}, h={b[3]}], area={b[4]}, vertices={b[5]}")

