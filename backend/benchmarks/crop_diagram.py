import cv2
from pathlib import Path

img = cv2.imread("backend/uploads/handwritten/13/processed/page_001.png")
# Crop region y=900..1850
diag_crop = img[900:1850, :]
out_path = Path("backend/benchmarks/artifacts/layout_40_visualizations/doc13_diagram_region.png")
out_path.parent.mkdir(parents=True, exist_ok=True)
cv2.imwrite(str(out_path), diag_crop)
print(f"Saved diagram crop: {out_path.name} ({diag_crop.shape[1]}x{diag_crop.shape[0]})")

