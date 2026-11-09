import sys
import os
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(str(backend_dir))

from app.services.handwriting.layout_intelligence_service import analyze_page_layout

samples = [
    ("Blank (Root 4)", "uploads/handwritten/4/processed/page_001.png"),
    ("Doc 10 (Poetry)", "uploads/handwritten/10/processed/page_001.png"),
    ("Doc 12 P1 (Networks)", "uploads/handwritten/12/processed/page_001.png"),
    ("Doc 13 (Web / Diagram)", "uploads/handwritten/13/processed/page_001.png"),
    ("Root 1 (Physics Title)", "uploads/handwritten/1/processed/page_001.png"),
    ("Root 3 (Math)", "uploads/handwritten/3/processed/page_001.png"),
]

for label, rel_path in samples:
    p = backend_dir / rel_path
    if not p.exists():
        print(f"Skipping {label}: {p} not found")
        continue
    res = analyze_page_layout(p, page_id=label)
    print(f"\n=== {label} ===")
    print(f"Empty: {res['is_empty']}, Total Regions: {res['total_regions']}, Time: {res['execution_time_ms']}ms")
    print(f"Counts: {res['counts_by_type']}")
    print(f"Has diagrams: {res['has_diagrams']}, Has formulas: {res['has_formulas']}, Has tables: {res['has_tables']}")
    for r in res['regions']:
        bx, by, bw, bh = r['bbox']
        print(f"  [{r['region_type'].upper()}] bbox=[x={bx}, y={by}, w={bw}, h={bh}] conf={r['confidence']}")

