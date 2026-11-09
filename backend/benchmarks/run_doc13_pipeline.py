import sys
import os
import time
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(str(backend_dir))

from app.services.handwriting.transcription_pipeline import transcribe_page_image

img_path = Path("uploads/handwritten/13/processed/page_001.png")
print("Transcribing Document #13 with production pipeline...")
t0 = time.time()
res = transcribe_page_image(img_path)
t1 = time.time()
print(f"Done in {t1-t0:.2f}s. Total lines: {len(res['lines'])}")
for i, l in enumerate(res['lines']):
    print(f"Line {i+1} [y={l['bbox'][1]}..{l['bbox'][1]+l['bbox'][3]}]: (conf {l['confidence']:.1f}) -> {l['text']}")

