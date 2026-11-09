import sys
import os
from pathlib import Path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(str(backend_dir))

import cv2
from PIL import Image
from app.services.handwriting.ocr_service import recognize_line_image

img_path = backend_dir / "benchmarks" / "artifacts" / "layout_40_visualizations" / "doc13_diagram_region.png"
img = cv2.imread(str(img_path))
h, w = img.shape[:2]

# Let's crop 10 vertical strips across the diagram region to see what text is in each strip
pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

strip_h = 90
for y_start in range(0, h - strip_h, 75):
    crop = pil_img.crop((50, y_start, w - 50, y_start + strip_h))
    res = recognize_line_image(crop)
    text = res.get("text", "").strip()
    conf = res.get("confidence", 0.0)
    print(f"y={y_start+900}..{y_start+strip_h+900} (conf: {conf:.1f}%): {text}")
