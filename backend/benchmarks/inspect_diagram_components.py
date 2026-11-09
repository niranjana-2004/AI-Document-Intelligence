import cv2
import numpy as np

img = cv2.imread("backend/benchmarks/artifacts/layout_40_visualizations/doc13_diagram_region.png")
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
_, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

# Find connected components
num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(thresh)
print(f"Num CCs: {num_labels}")

# Let's inspect CCs with width between 50 and 600, height between 30 and 200
boxes = []
arrows = []
for i in range(1, num_labels):
    x, y, w, h, area = stats[i]
    aspect = w / max(1, h)
    density = area / max(1, w * h)
    # Check if box
    if w > 80 and h > 30 and density < 0.35:
        boxes.append((x, y + 900, w, h, area, aspect, density))
    elif (aspect > 3.0 or aspect < 0.3) and max(w, h) > 40:
        arrows.append((x, y + 900, w, h, area, aspect, density))

print(f"Detected {len(boxes)} boxes:")
for b in boxes:
    print(f"  Box at y={b[1]}..{b[1]+b[3]}, x={b[0]}..{b[0]+b[2]}, w={b[2]}, h={b[3]}, density={b[6]:.2f}")

print(f"\nDetected {len(arrows)} arrows/connectors:")
for a in arrows:
    print(f"  Connector at y={a[1]}..{a[1]+a[3]}, x={a[0]}..{a[0]+a[2]}, w={a[2]}, h={a[3]}, aspect={a[5]:.2f}")

