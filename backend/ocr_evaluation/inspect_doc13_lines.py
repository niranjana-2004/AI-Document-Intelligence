import os, sys
import cv2
from pathlib import Path

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

from app.services.handwriting.transcription_pipeline import transcribe_page_image

p = Path("D:/AI-Document-Intelligence/backend/uploads/handwritten/13/processed/page_001.png")
res = transcribe_page_image(p)

print(f"Total lines: {res['total_lines']}")
for idx, l in enumerate(res["lines"]):
    box = l.get("bbox", [])
    txt = l.get("text", "")
    conf = l.get("confidence", 0)
    print(f"L{idx+1:02d} [conf={conf:.1f}%] [y={box[1]} h={box[3]}]: {txt}")

