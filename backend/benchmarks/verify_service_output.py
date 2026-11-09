import sys
import os
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(str(backend_dir))

from app.services.handwriting.layout_intelligence_service import analyze_page_layout

def test_page(label, path_str):
    p = Path(path_str)
    if not p.exists():
        p = backend_dir / path_str
    if not p.exists():
        p = Path("D:/AI-Document-Intelligence") / path_str
    if not p.exists():
        print(f"Skipping {label}: {path_str} not found")
        return

    res = analyze_page_layout(p, page_id=label)
    print(f"\n======================================")
    print(f"{label} ({res['width']}x{res['height']}) - {res['execution_time_ms']}ms")
    print(f"Empty: {res['is_empty']}, Total Regions: {res['total_regions']}")
    print(f"Counts: {res['counts_by_type']}")
    print(f"Has Diagram: {res['has_diagrams']}, Has Formula: {res['has_formulas']}, Has Table: {res['has_tables']}")
    for r in res['regions']:
        bx, by, bw, bh = r['bbox']
        print(f"  [{r['region_type'].upper()}] bbox=[x={bx}, y={by}, w={bw}, h={bh}] (conf: {r['confidence']})")

test_page("Blank (Root 4)", "uploads/handwritten/4/processed/page_001.png")
test_page("Doc 10 (Poetry)", "backend/uploads/handwritten/10/processed/page_001.png")
test_page("Doc 12 P1 (Networks)", "backend/uploads/handwritten/12/processed/page_001.png")
test_page("Doc 13 (CSS Diagram)", "backend/uploads/handwritten/13/processed/page_001.png")
test_page("Root 1 (Physics Title)", "uploads/handwritten/1/processed/page_001.png")
test_page("Root 3 (Math)", "uploads/handwritten/3/processed/page_001.png")

