import cv2
import numpy as np

img = cv2.imread("backend/uploads/handwritten/13/processed/page_001.png")
h, w = img.shape[:2]
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
_, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

# Test kernel lengths: 100, 150, 200, 250
for k_len in [80, 120, 160, 200]:
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (k_len, 2))
    opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, k)
    print(f"Kernel len {k_len}:")
    print(f"  Upper half (y < 950) ink: {np.sum(opened[:950, :] > 0)}")
    print(f"  Lower half (y >= 950) ink: {np.sum(opened[950:, :] > 0)}")

