import cv2
import numpy as np
from pathlib import Path

img_path = Path("backend/uploads/handwritten/13/processed/page_001.png")
img = cv2.imread(str(img_path))
h, w = img.shape[:2]
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# Otsu threshold
blur = cv2.GaussianBlur(gray, (5, 5), 0)
_, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

print(f"Image shape: {w}x{h}")
total_ink = np.sum(thresh > 0)
print(f"Total ink pixels: {total_ink} ({total_ink / (w*h) * 100:.2f}%)")

# Horizontal projection profile
row_ink = np.sum(thresh > 0, axis=1)

# Check upper half vs lower half
split_y = int(h * 0.52)
print(f"\nUpper half (0..{split_y}) ink: {np.sum(thresh[:split_y] > 0)}")
print(f"Lower half ({split_y}..{h}) ink: {np.sum(thresh[split_y:] > 0)}")

# Find horizontal and vertical lines (morphological)
line_len_h = int(w * 0.08)
kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (line_len_h, 1))
h_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_h)
print(f"Horizontal line pixels: {np.sum(h_lines > 0)}")

line_len_v = int(h * 0.04)
kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, line_len_v))
v_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_v)
print(f"Vertical line pixels: {np.sum(v_lines > 0)}")

# Find rectangular boxes / contours
combined_lines = cv2.add(h_lines, v_lines)
contours, _ = cv2.findContours(combined_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
print(f"\nDetected {len(contours)} line/box contours:")
for i, c in enumerate(contours):
    x, y, bw, bh = cv2.boundingRect(c)
    area = cv2.contourArea(c)
    rect_area = bw * bh
    extent = area / rect_area if rect_area > 0 else 0
    print(f"Contour {i+1}: bbox=[x={x}, y={y}, w={bw}, h={bh}], area={area}, extent={extent:.2f}")

