import os
import sys
from pathlib import Path

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

from app.services.handwriting.transcription_pipeline import transcribe_page_image

project_root = Path("D:/AI-Document-Intelligence")

test_samples = [
    ("Doc 10 (Poem/General)", project_root / "backend/uploads/handwritten/10/processed/page_001.png"),
    ("Doc 13 (CSS/Web Notes)", project_root / "backend/uploads/handwritten/13/processed/page_001.png"),
    ("Root 1 (Physics)", project_root / "uploads/handwritten/1/processed/page_001.png"),
    ("Root 2 P1 (Lecture)", project_root / "uploads/handwritten/2/processed/page_001.png"),
    ("Root 2 P2 (Lecture)", project_root / "uploads/handwritten/2/processed/page_002.png"),
    ("Root 3 (Faint Math)", project_root / "uploads/handwritten/3/processed/page_001.png"),
    ("Root 4 (Blank Page)", project_root / "uploads/handwritten/4/processed/page_001.png"),
]

for label, p in test_samples:
    abs_p = p.resolve()
    print(f"\n==================== {label} ====================")
    print(f"Path: {abs_p} | Exists: {abs_p.exists()}")
    if abs_p.exists():
        try:
            res = transcribe_page_image(abs_p)
            print(f"  Confidence: {res['confidence_score']}% | Lines: {res['total_lines']} | Empty: {res['is_empty']}")
            print(f"  Corrs: {len(res.get('technical_corrections', []))}")
            lines = res.get("lines", [])
            for i, l in enumerate(lines[:5]):
                print(f"    Line {i+1}: {repr(l.get('text', ''))[:80]}")
            if len(lines) > 5:
                print(f"    ... and {len(lines)-5} more lines")
        except Exception as e:
            print(f"  Error: {e}")

