import cv2
import numpy as np
from pathlib import Path

def resolve_path(p_str: str) -> Path:
    p = Path(p_str)
    if p.exists():
        return p
    p_b = Path("backend") / p_str
    if p_b.exists():
        return p_b
    p_r = Path("D:/AI-Document-Intelligence") / p_str
    if p_r.exists():
        return p_r
    return p

test_samples = [
    ("Blank (Root 4)", "uploads/handwritten/4/processed/page_001.png"),
    ("Doc 10 (Poetry)", "backend/uploads/handwritten/10/processed/page_001.png"),
    ("Doc 12 P1 (TCP Notes)", "backend/uploads/handwritten/12/processed/page_001.png"),
    ("Doc 12 P2 (TCP Notes)", "backend/uploads/handwritten/12/processed/page_002.png"),
    ("Doc 13 (CSS Diagram)", "backend/uploads/handwritten/13/processed/page_001.png"),
    ("Root 1 (Physics)", "uploads/handwritten/1/processed/page_001.png"),
    ("Root 2 P1 (Lecture)", "uploads/handwritten/2/processed/page_001.png"),
    ("Root 3 (Math)", "uploads/handwritten/3/processed/page_001.png"),
]

for label, path_str in test_samples:
    p = resolve_path(path_str)
    print(f"{label}: {p} -> exists: {p.exists()}")

