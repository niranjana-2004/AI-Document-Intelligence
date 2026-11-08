import os, sys
from pathlib import Path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

from app.services.handwriting.transcription_pipeline import transcribe_page_image
from benchmark_ocr import levenshtein_distance

img = Path("D:/AI-Document-Intelligence/backend/uploads/handwritten/10/processed/page_001.png")
res = transcribe_page_image(img, subject="General Literature")

gt = open("ground_truth/doc10_p01.txt", "r", encoding="utf-8").read().strip()
raw = res.get("raw_text", "")
rec = res["full_text"]

print(f"Raw CER: {levenshtein_distance(list(gt), list(raw)) / len(gt) * 100:.2f}%")
print(f"Rec CER: {levenshtein_distance(list(gt), list(rec)) / len(gt) * 100:.2f}%")
print("\nCorrections count:", len(res.get("technical_corrections", [])))
for c in res.get("technical_corrections", []):
    print(" ", c.get("id"), c.get("type"), repr(c.get("original_text")), "->", repr(c.get("suggested_text")), c.get("status"), c.get("confidence"))

print("\n--- RAW DIFF ---")
import difflib
print("\n".join(difflib.unified_diff(gt.splitlines(), raw.splitlines(), lineterm="")))
print("\n--- REC DIFF ---")
print("\n".join(difflib.unified_diff(gt.splitlines(), rec.splitlines(), lineterm="")))

