import sys
import os
from pathlib import Path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(str(backend_dir))

import cv2
from app.services.handwriting.image_preprocessor import read_image_safe
from app.services.handwriting.line_segmenter import segment_page_into_lines

img_path = Path("backend/uploads/handwritten/13/processed/page_001.png")
if not img_path.exists():
    img_path = Path("uploads/handwritten/13/processed/page_001.png")

img = read_image_safe(img_path)
line_crops, is_empty = segment_page_into_lines(img)
print(f"Total line crops: {len(line_crops)}, is_empty: {is_empty}")
for i, c in enumerate(line_crops):
    print(f"Line {i+1}: bbox={c.bbox}")

