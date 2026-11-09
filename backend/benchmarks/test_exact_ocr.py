import sys
import os
from pathlib import Path

backend_dir = Path("backend").resolve()
sys.path.insert(0, str(backend_dir))
os.chdir(str(backend_dir))

import cv2
import numpy as np
from app.services.handwriting.transcription_pipeline import transcribe_page_image
from benchmark_ocr import calculate_cer, calculate_wer

gt_path = backend_dir / "ground_truth" / "doc13_p01.txt"
ground_truth = gt_path.read_text(encoding="utf-8").strip()

img_path = backend_dir / "uploads" / "handwritten" / "13" / "processed" / "page_001.png"
img = cv2.imread(str(img_path))

text_1 = img[0:1066, :]
text_2 = img[1812:2000, :]
exp_img = np.vstack([text_1, text_2])
exp_path = backend_dir / "benchmarks" / "artifacts" / "layout_40_visualizations" / "doc13_exact_text.png"
cv2.imwrite(str(exp_path), exp_img)

res_exp = transcribe_page_image(exp_path)
text_exp = res_exp.get("recovered_text", "")

cer_exp = calculate_cer(ground_truth, text_exp)
wer_exp = calculate_wer(ground_truth, text_exp)
print(f"Exact Text Only: CER={cer_exp*100:.2f}%, WER={wer_exp*100:.2f}%")
print(f"Lines count: {len(res_exp['lines'])}")

