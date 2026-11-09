import cv2
from pathlib import Path

img = cv2.imread("backend/uploads/handwritten/13/processed/page_001.png")
h, w = img.shape[:2]

gt_regions = {
    "gt_title": (40, 0, 1340, 125),
    "gt_heading": (40, 125, 1340, 130),
    "gt_body_text": (40, 255, 1340, 685),
    "gt_diagram": (40, 940, 1340, 870),
    "gt_footer_text": (40, 1810, 1340, 190)
}

out_dir = Path("backend/benchmarks/artifacts/layout_40_visualizations/gt_crops")
out_dir.mkdir(parents=True, exist_ok=True)

for name, (x, y, bw, bh) in gt_regions.items():
    crop = img[y:y+bh, x:x+bw]
    out_file = out_dir / f"{name}.png"
    cv2.imwrite(str(out_file), crop)
    print(f"Saved {name}: bbox=[{x}, {y}, {bw}, {bh}], shape={crop.shape}")

