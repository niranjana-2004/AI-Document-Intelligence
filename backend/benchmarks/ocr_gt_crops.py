import sys
import os
from pathlib import Path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(str(backend_dir))

from app.services.handwriting.transcription_pipeline import transcribe_page_image

gt_dir = backend_dir / "benchmarks" / "artifacts" / "layout_40_visualizations" / "gt_crops"

for name in ["gt_title", "gt_heading", "gt_footer_text"]:
    crop_path = gt_dir / f"{name}.png"
    res = transcribe_page_image(crop_path)
    text = res.get("recovered_text", "").strip()
    print(f"\n=== {name} ===")
    print(text)

