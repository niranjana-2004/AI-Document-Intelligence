import json
import cv2
from pathlib import Path

backend_dir = Path("backend").resolve()

samples_data = [
    {
        "sample_id": "doc13_p01",
        "document_id": "13",
        "page_number": 1,
        "image_path": "backend/uploads/handwritten/13/processed/page_001.png",
        "ground_truth_text_path": "backend/ground_truth/doc13_p01.txt",
        "subject": "Web Development & CSS Architecture Flowchart",
        "style": "handwritten_notes_and_diagram",
        "expected_non_text": True,
        "ground_truth_regions": [
            {"id": "gt_heading_1", "region_type": "heading", "bbox": [40, 0, 1340, 125], "description": "Title: 1. Introduction to CSS"},
            {"id": "gt_heading_2", "region_type": "heading", "bbox": [40, 125, 1340, 130], "description": "Subheading: What is CSS, and its role in web development"},
            {"id": "gt_text_1", "region_type": "text", "bbox": [40, 255, 1340, 811], "description": "Body text lines 3-14 (CSS definitions, types of CSS)"},
            {"id": "gt_diagram_1", "region_type": "diagram", "bbox": [40, 1066, 1340, 746], "description": "CSS flowchart diagram with boxes, connectors, code block"},
            {"id": "gt_text_2", "region_type": "text", "bbox": [40, 1812, 1340, 188], "description": "Footer text lines 15-16 (Inline CSS discouragement note)"}
        ]
    },
    {
        "sample_id": "doc12_p01",
        "document_id": "12",
        "page_number": 1,
        "image_path": "backend/uploads/handwritten/12/processed/page_001.png",
        "ground_truth_text_path": "backend/ground_truth/page_001.txt",
        "subject": "Computer Networks — TCP Transmission Control Protocol",
        "style": "lined_notebook_technical_notes",
        "expected_non_text": False,
        "ground_truth_regions": [
            {"id": "gt_heading_1", "region_type": "heading", "bbox": [40, 170, 1800, 230], "description": "Title & Topic Heading"},
            {"id": "gt_text_1", "region_type": "text", "bbox": [40, 400, 1800, 1750], "description": "Computer Networks TCP body paragraphs"}
        ]
    },
    {
        "sample_id": "doc12_p02",
        "document_id": "12",
        "page_number": 2,
        "image_path": "backend/uploads/handwritten/12/processed/page_002.png",
        "ground_truth_text_path": "backend/ground_truth/page_002.txt",
        "subject": "Computer Networks — TCP Header & Operation",
        "style": "lined_notebook_technical_notes",
        "expected_non_text": False,
        "ground_truth_regions": [
            {"id": "gt_heading_1", "region_type": "heading", "bbox": [40, 170, 1800, 200], "description": "Page heading"},
            {"id": "gt_text_1", "region_type": "text", "bbox": [40, 370, 1800, 1780], "description": "TCP technical notes body text"}
        ]
    },
    {
        "sample_id": "doc12_p03",
        "document_id": "12",
        "page_number": 3,
        "image_path": "backend/uploads/handwritten/12/processed/page_003.png",
        "ground_truth_text_path": "backend/ground_truth/page_003.txt",
        "subject": "Computer Networks — Three-Way Handshake",
        "style": "lined_notebook_technical_notes",
        "expected_non_text": False,
        "ground_truth_regions": [
            {"id": "gt_heading_1", "region_type": "heading", "bbox": [40, 170, 1800, 200], "description": "Page heading"},
            {"id": "gt_text_1", "region_type": "text", "bbox": [40, 370, 1800, 1780], "description": "Handshake mechanism notes"}
        ]
    },
    {
        "sample_id": "doc12_p04",
        "document_id": "12",
        "page_number": 4,
        "image_path": "backend/uploads/handwritten/12/processed/page_004.png",
        "ground_truth_text_path": "backend/ground_truth/page_004.txt",
        "subject": "Computer Networks — Sliding Window & Flow Control",
        "style": "lined_notebook_technical_notes",
        "expected_non_text": False,
        "ground_truth_regions": [
            {"id": "gt_heading_1", "region_type": "heading", "bbox": [40, 170, 1800, 200], "description": "Page heading"},
            {"id": "gt_text_1", "region_type": "text", "bbox": [40, 370, 1800, 1780], "description": "Flow control body paragraphs"}
        ]
    },
    {
        "sample_id": "doc12_p05",
        "document_id": "12",
        "page_number": 5,
        "image_path": "backend/uploads/handwritten/12/processed/page_005.png",
        "ground_truth_text_path": "backend/ground_truth/page_005.txt",
        "subject": "Computer Networks — Congestion Control",
        "style": "lined_notebook_technical_notes",
        "expected_non_text": False,
        "ground_truth_regions": [
            {"id": "gt_heading_1", "region_type": "heading", "bbox": [40, 170, 1800, 200], "description": "Page heading"},
            {"id": "gt_text_1", "region_type": "text", "bbox": [40, 370, 1800, 1780], "description": "Congestion control body text"}
        ]
    },
    {
        "sample_id": "doc12_p06",
        "document_id": "12",
        "page_number": 6,
        "image_path": "backend/uploads/handwritten/12/processed/page_006.png",
        "ground_truth_text_path": "backend/ground_truth/page_006.txt",
        "subject": "Computer Networks — Connection Termination",
        "style": "lined_notebook_technical_notes",
        "expected_non_text": False,
        "ground_truth_regions": [
            {"id": "gt_heading_1", "region_type": "heading", "bbox": [40, 170, 1800, 200], "description": "Page heading"},
            {"id": "gt_text_1", "region_type": "text", "bbox": [40, 370, 1800, 1780], "description": "Termination body text"}
        ]
    },
    {
        "sample_id": "doc12_p07",
        "document_id": "12",
        "page_number": 7,
        "image_path": "backend/uploads/handwritten/12/processed/page_007.png",
        "ground_truth_text_path": "backend/ground_truth/page_007.txt",
        "subject": "Computer Networks — Summary & Protocol Properties",
        "style": "lined_notebook_technical_notes",
        "expected_non_text": False,
        "ground_truth_regions": [
            {"id": "gt_heading_1", "region_type": "heading", "bbox": [40, 170, 1800, 200], "description": "Page heading"},
            {"id": "gt_text_1", "region_type": "text", "bbox": [40, 370, 1800, 1400], "description": "Protocol summary body text"}
        ]
    },
    {
        "sample_id": "doc10_p01",
        "document_id": "10",
        "page_number": 1,
        "image_path": "backend/uploads/handwritten/10/processed/page_001.png",
        "ground_truth_text_path": "backend/ground_truth/doc10_p01.txt",
        "subject": "Poetry — The Road Not Taken",
        "style": "cursive_literary_manuscript",
        "expected_non_text": False,
        "ground_truth_regions": [
            {"id": "gt_heading_1", "region_type": "heading", "bbox": [60, 90, 1000, 140], "description": "Poem title"},
            {"id": "gt_text_1", "region_type": "text", "bbox": [60, 230, 1050, 930], "description": "Poetry stanzas"}
        ]
    },
    {
        "sample_id": "root1_p01",
        "document_id": "1",
        "page_number": 1,
        "image_path": "uploads/handwritten/1/processed/page_001.png",
        "ground_truth_text_path": "backend/ground_truth/root1_p01.txt",
        "subject": "Physics Lecture Notes — Quantum Mechanics",
        "style": "plain_paper_notes",
        "expected_non_text": False,
        "ground_truth_regions": [
            {"id": "gt_heading_1", "region_type": "heading", "bbox": [20, 40, 360, 60], "description": "Header title"},
            {"id": "gt_text_1", "region_type": "text", "bbox": [20, 160, 450, 60], "description": "Topic subtitle"}
        ]
    },
    {
        "sample_id": "root2_p01",
        "document_id": "2",
        "page_number": 1,
        "image_path": "uploads/handwritten/2/processed/page_001.png",
        "ground_truth_text_path": "backend/ground_truth/root2_p01.txt",
        "subject": "Physics Notes — Quantum Mechanics",
        "style": "plain_paper_notes",
        "expected_non_text": False,
        "ground_truth_regions": [
            {"id": "gt_heading_1", "region_type": "heading", "bbox": [80, 150, 960, 100], "description": "Title: Physics Lecture Notes"},
            {"id": "gt_text_1", "region_type": "text", "bbox": [80, 260, 1200, 310], "description": "Topic subtitle: Quantum Mechanics Principles"}
        ]
    },
    {
        "sample_id": "root2_p02",
        "document_id": "2",
        "page_number": 2,
        "image_path": "uploads/handwritten/2/processed/page_002.png",
        "ground_truth_text_path": "backend/ground_truth/root2_p02.txt",
        "subject": "Thermodynamics Laws",
        "style": "plain_paper_notes",
        "expected_non_text": False,
        "ground_truth_regions": [
            {"id": "gt_heading_1", "region_type": "heading", "bbox": [80, 150, 980, 100], "description": "Topic header: Thermodynamics laws"}
        ]
    },
    {
        "sample_id": "root3_p01",
        "document_id": "3",
        "page_number": 1,
        "image_path": "uploads/handwritten/3/processed/page_001.png",
        "ground_truth_text_path": "backend/ground_truth/root3_p01.txt",
        "subject": "Differential Equations",
        "style": "plain_paper_notes",
        "expected_non_text": False,
        "ground_truth_regions": [
            {"id": "gt_text_1", "region_type": "text", "bbox": [20, 70, 270, 60], "description": "Differential equations body text"}
        ]
    },
    {
        "sample_id": "root4_p01",
        "document_id": "4",
        "page_number": 1,
        "image_path": "uploads/handwritten/4/processed/page_001.png",
        "ground_truth_text_path": "backend/ground_truth/root4_p01.txt",
        "subject": "Blank Negative Control",
        "style": "blank_empty_paper",
        "expected_non_text": False,
        "is_negative_control": True,
        "ground_truth_regions": [
            {"id": "gt_bg_1", "region_type": "background", "bbox": [0, 0, 400, 400], "description": "Empty blank background"}
        ]
    }
]

# Enrich with image dimensions
for s in samples_data:
    p = Path(s["image_path"])
    if not p.exists():
        p = Path("D:/AI-Document-Intelligence") / s["image_path"]
    img = cv2.imread(str(p))
    if img is not None:
        h, w = img.shape[:2]
        s["dimensions"] = {"width": w, "height": h}
    else:
        print(f"Warning: could not read {p}")

manifest = {
    "version": "4.0",
    "milestone": "Phase A: Region Detection & Layout Benchmark",
    "total_samples": len(samples_data),
    "samples": samples_data
}

manifest_path = backend_dir / "benchmarks" / "layout_intelligence_manifest.json"
manifest_path.parent.mkdir(parents=True, exist_ok=True)
manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(f"Manifest written to {manifest_path} with {len(samples_data)} samples.")
