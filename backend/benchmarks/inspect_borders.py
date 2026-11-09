import cv2
import numpy as np

img = cv2.imread("backend/uploads/handwritten/13/processed/page_001.png")
h, w = img.shape[:2]
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
_, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

# Check ink on borders: x=0..15, x=w-15..w, y=0..15, y=h-15..h
print("Left border ink (x<10):", np.sum(thresh[:, :10] > 0))
print("Right border ink (x>w-10):", np.sum(thresh[:, -10:] > 0))
print("Top border ink (y<10):", np.sum(thresh[:10, :] > 0))
print("Bottom border ink (y>h-10):", np.sum(thresh[-10:, :] > 0))

# Sample rows in the bottom half
for y_test in [1000, 1150, 1300, 1450, 1600, 1750, 1900]:
    row = thresh[y_test, :]
    print(f"Row {y_test} ink pixels: {np.sum(row > 0)} out of {w}")

