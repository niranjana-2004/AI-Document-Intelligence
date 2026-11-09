import cv2
import numpy as np

img = cv2.imread("backend/uploads/handwritten/13/processed/page_001.png")
h, w = img.shape[:2]
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
blur = cv2.GaussianBlur(gray, (5, 5), 0)
_, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

def max_contiguous_run(row: np.ndarray) -> int:
    runs = []
    curr = 0
    for val in row:
        if val > 0:
            curr += 1
        else:
            if curr > 0:
                runs.append(curr)
                curr = 0
    if curr > 0:
        runs.append(curr)
    return max(runs) if runs else 0

# Check max contiguous run for rows in upper half (text) vs lower half (diagram)
runs_upper = [max_contiguous_run(thresh[y, :]) for y in range(0, 950)]
runs_lower = [max_contiguous_run(thresh[y, :]) for y in range(950, 1850)]

print(f"Upper half (Text) - Max run: {max(runs_upper)}, 99th percentile: {np.percentile(runs_upper, 99):.1f}")
print(f"Lower half (Diagram) - Max run: {max(runs_lower)}, 99th percentile: {np.percentile(runs_lower, 99):.1f}")

# Rows with unbroken runs > 150 px:
long_run_rows_upper = [y for y in range(0, 950) if max_contiguous_run(thresh[y, :]) > 150]
long_run_rows_lower = [y for y in range(950, 1850) if max_contiguous_run(thresh[y, :]) > 150]

print(f"Rows with continuous run > 150px in Upper half: {len(long_run_rows_upper)}")
print(f"Rows with continuous run > 150px in Lower half: {len(long_run_rows_lower)}")
for y in long_run_rows_lower[:15]:
    print(f"  Diagram row y={y}: run={max_contiguous_run(thresh[y, :])}px")

