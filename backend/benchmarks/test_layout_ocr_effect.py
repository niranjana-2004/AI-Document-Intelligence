import sys
import os
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(str(backend_dir))

import cv2
import numpy as np
from app.services.handwriting.transcription_pipeline import transcribe_page_image
from benchmark_ocr import calculate_cer, calculate_wer

gt_path = backend_dir / "ground_truth" / "doc13_p01.txt"
with open(gt_path, "r", encoding="utf-8") as f:
    ground_truth = f.read().strip()

img_path = backend_dir / "uploads" / "handwritten" / "13" / "processed" / "page_001.png"
img = cv2.imread(str(img_path))
h, w = img.shape[:2]

# Baseline transcription (full page)
print("1. Running full-page baseline transcription...")
res_base = transcribe_page_image(img_path)
text_base = res_base.get("recovered_text", "")

cer_base = calculate_cer(ground_truth, text_base)
wer_base = calculate_wer(ground_truth, text_base)
print(f"Baseline: CER={cer_base*100:.2f}%, WER={wer_base*100:.2f}%")
print(f"Lines count: {len(res_base['lines'])}")

# Experimental: Crop text regions only
# Text Region 1: y=0..940
# Text Region 2: y=1800..2000
text_region_1 = img[0:940, :]
text_region_2 = img[1800:2000, :]

# Stack text regions vertically (excluding diagram y=940..1800)
exp_img = np.vstack([text_region_1, text_region_2])
exp_path = backend_dir / "benchmarks" / "artifacts" / "layout_40_visualizations" / "doc13_text_only.png"
exp_path.parent.mkdir(parents=True, exist_ok=True)
cv2.imwrite(str(exp_path), exp_img)

print("\n2. Running experimental text-only transcription...")
res_exp = transcribe_page_image(exp_path)
text_exp = res_exp.get("recovered_text", "")

cer_exp = calculate_cer(ground_truth, text_exp)
wer_exp = calculate_wer(ground_truth, text_exp)
print(f"Experimental (Text Regions Only): CER={cer_exp*100:.2f}%, WER={wer_exp*100:.2f}%")
print(f"Lines count: {len(res_exp['lines'])}")
print(f"\nDelta CER: {(cer_exp - cer_base)*100:+.2f}%")
print(f"Delta WER: {(wer_exp - wer_base)*100:+.2f}%")
