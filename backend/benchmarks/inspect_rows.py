import cv2
import numpy as np

img = cv2.imread("backend/uploads/handwritten/13/processed/page_001.png")
h, w = img.shape[:2]
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
_, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

# Inspect rows 260..280
print("Rows 260..280 ink:")
for y in range(260, 280, 2):
    row = thresh[y, :]
    print(f"y={y}: non-zero={np.sum(row > 0)}")

# Inspect rows 920..945
print("\nRows 920..945 ink:")
for y in range(920, 945, 2):
    row = thresh[y, :]
    print(f"y={y}: non-zero={np.sum(row > 0)}")

