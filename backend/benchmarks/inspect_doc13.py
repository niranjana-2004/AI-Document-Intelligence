import sys
from pathlib import Path
import json
sys.path.insert(0, str(Path("backend").resolve()))

from app.services.handwriting.transcription_pipeline import transcribe_page_image

img_path = Path("backend/uploads/handwritten/13/processed/page_001.png")
res = transcribe_page_image(img_path)
print("Total lines:", len(res["lines"]))
for i, l in enumerate(res["lines"]):
    bx, by, bw, bh = l["bbox"]
    print(f"Line {i+1} [y={by}..{by+bh}, x={bx}..{bx+bw}, h={bh}] (conf: {l['confidence']:.1f}%): {l['text']}")

