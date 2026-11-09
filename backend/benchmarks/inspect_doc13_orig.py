import cv2
import numpy as np
from pathlib import Path

orig = cv2.imread("backend/uploads/handwritten/13/original/page_001.png")
proc = cv2.imread("backend/uploads/handwritten/13/processed/page_001.png")

print(f"Original shape: {orig.shape if orig is not None else 'None'}")
print(f"Processed shape: {proc.shape if proc is not None else 'None'}")

# Check color channels in original
# Let's see if there are ruling lines or page borders in original
gray_orig = cv2.cvtColor(orig, cv2.COLOR_BGR2GRAY)
_, thresh_orig = cv2.threshold(gray_orig, 200, 255, cv2.THRESH_BINARY_INV)
print("Thresh orig non-zero:", np.sum(thresh_orig > 0))

# Sample 10 vertical strips across the width
for x_sample in [50, 200, 400, 700, 1000, 1200, 1350]:
    col = thresh_orig[:, x_sample]
    print(f"Column x={x_sample} non-zero: {np.sum(col > 0)} / {orig.shape[0]}")

