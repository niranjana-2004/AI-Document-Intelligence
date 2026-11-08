import os, sys
from pathlib import Path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

from app.services.handwriting.transcription_pipeline import transcribe_page_image

project_root = Path("D:/AI-Document-Intelligence")

print("=== DOC 10 ALL LINES ===")
res10 = transcribe_page_image(project_root / "backend/uploads/handwritten/10/processed/page_001.png")
for idx, l in enumerate(res10["lines"]):
    print(f"L{idx+1:02d}: {l['text']}")

print("\n=== DOC 13 ALL LINES ===")
res13 = transcribe_page_image(project_root / "backend/uploads/handwritten/13/processed/page_001.png", subject="Computer Science & Networking")
for idx, l in enumerate(res13["lines"]):
    print(f"L{idx+1:02d}: {l['text']}")

