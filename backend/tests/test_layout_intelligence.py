"""
Unit tests for Cognidocs Layout Intelligence 4.0 — Phase A
Tests local CPU region detection, negative control, data models, visualizer, and non-destructive execution.
"""

import sys
import os
import time
from pathlib import Path
import numpy as np
import cv2

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(str(backend_dir))

from app.services.handwriting.layout_intelligence_service import (
    analyze_page_layout,
    Region,
    REGION_TEXT,
    REGION_HEADING,
    REGION_DIAGRAM,
    REGION_BACKGROUND,
    REGION_TABLE,
    REGION_FORMULA,
    VALID_REGION_TYPES
)
from app.services.handwriting.layout_visualizer import render_detailed_layout, render_simplified_layout
from app.services.handwriting.transcription_pipeline import transcribe_page_image


def test_01_blank_page_negative_control():
    """Test 1: Blank page (Root 4) must return is_empty=True, 0 false text/diagram regions, 1 background region."""
    blank_path = backend_dir.parent / "uploads" / "handwritten" / "4" / "processed" / "page_001.png"
    if not blank_path.exists():
        blank_path = Path("uploads/handwritten/4/processed/page_001.png")
    assert blank_path.exists(), f"Blank test file missing at {blank_path}"

    res = analyze_page_layout(str(blank_path), page_id="root4_p01")
    assert res["is_empty"] is True
    assert res["total_regions"] == 1
    assert res["counts_by_type"].get(REGION_BACKGROUND) == 1
    assert res["has_diagrams"] is False
    assert res["has_formulas"] is False
    assert res["has_tables"] is False
    assert len(res["text_regions"]) == 0
    assert len(res["non_text_regions"]) == 1


def test_02_doc13_diagram_detection():
    """Test 2: Document #13 diagram detected, isolating flowchart boxes and connectors with IoU > 0.70."""
    doc13_path = backend_dir / "uploads" / "handwritten" / "13" / "processed" / "page_001.png"
    assert doc13_path.exists(), f"Doc 13 image missing at {doc13_path}"

    res = analyze_page_layout(str(doc13_path), page_id="doc13_p01")
    assert res["is_empty"] is False
    assert res["has_diagrams"] is True

    diagram_regs = [r for r in res["regions"] if r["region_type"] == REGION_DIAGRAM]
    assert len(diagram_regs) >= 1, "Flowchart diagram region not detected"

    # Ground truth diagram bbox is approx [40, 1066, 1340, 746]
    diag_bbox = diagram_regs[0]["bbox"]
    gt_bbox = (40, 1066, 1340, 746)

    # Compute IoU
    xA = max(diag_bbox[0], gt_bbox[0])
    yA = max(diag_bbox[1], gt_bbox[1])
    xB = min(diag_bbox[0] + diag_bbox[2], gt_bbox[0] + gt_bbox[2])
    yB = min(diag_bbox[1] + diag_bbox[3], gt_bbox[1] + gt_bbox[3])
    inter = max(0, xB - xA) * max(0, yB - yA)
    union = (diag_bbox[2] * diag_bbox[3]) + (gt_bbox[2] * gt_bbox[3]) - inter
    iou = inter / float(union) if union > 0 else 0.0

    assert iou > 0.70, f"Diagram IoU {iou:.3f} is below 0.70 threshold"
    assert diagram_regs[0]["confidence"] >= 0.85


def test_03_heading_vs_text_differentiation():
    """Test 3: Headings at top of page differentiated from body paragraphs."""
    doc10_path = backend_dir / "uploads" / "handwritten" / "10" / "processed" / "page_001.png"
    res = analyze_page_layout(str(doc10_path), page_id="doc10_p01")
    assert res["counts_by_type"].get(REGION_HEADING, 0) >= 1
    assert res["counts_by_type"].get(REGION_TEXT, 0) >= 1

    heading = next(r for r in res["regions"] if r["region_type"] == REGION_HEADING)
    body = next(r for r in res["regions"] if r["region_type"] == REGION_TEXT)

    # Heading must be above body text
    assert heading["bbox"][1] < body["bbox"][1]
    assert heading["heading_likelihood"] > heading["text_likelihood"]
    assert body["text_likelihood"] > body["heading_likelihood"]


def test_04_region_data_model_integrity():
    """Test 4: Region dataclass model integrity, serialization, and deserialization."""
    reg = Region(
        id="reg_test_1",
        page_id="p1",
        region_type=REGION_TEXT,
        bbox=(10, 20, 200, 100),
        polygon=[(10, 20), (210, 20), (210, 120), (10, 120)],
        confidence=0.95,
        area_ratio=0.05,
        stroke_density=0.12,
        aspect_ratio=2.0,
        text_likelihood=0.96,
        detection_evidence={"test_evidence": True}
    )

    d = reg.to_dict()
    assert d["id"] == "reg_test_1"
    assert d["region_type"] == REGION_TEXT
    assert d["bbox"] == [10, 20, 200, 100]
    assert len(d["polygon"]) == 4
    assert 0.0 <= d["confidence"] <= 1.0

    deser = Region.from_dict(d)
    assert deser.id == reg.id
    assert deser.bbox == reg.bbox
    assert deser.confidence == reg.confidence
    assert deser.region_type in VALID_REGION_TYPES


def test_05_visualizer_rendering(tmp_path=None):
    """Test 5: Visualizer correctly generates detailed and simplified layout image overlays."""
    if tmp_path is None:
        tmp_path = backend_dir / "benchmarks" / "artifacts" / "layout_40_visualizations" / "test_tmp"
    tmp_path.mkdir(parents=True, exist_ok=True)
    dummy_img = np.ones((500, 500, 3), dtype=np.uint8) * 240
    dummy_regions = [
        {
            "id": "h_1",
            "region_type": "heading",
            "bbox": [50, 20, 400, 60],
            "confidence": 0.92,
            "polygon": [[50, 20], [450, 20], [450, 80], [50, 80]]
        },
        {
            "id": "d_1",
            "region_type": "diagram",
            "bbox": [50, 120, 400, 300],
            "confidence": 0.90,
            "polygon": [[50, 120], [450, 120], [450, 420], [50, 420]]
        }
    ]

    detailed_path = tmp_path / "test_detailed.png"
    simplified_path = tmp_path / "test_simplified.png"

    render_detailed_layout(dummy_img, dummy_regions, detailed_path)
    render_simplified_layout(dummy_img, dummy_regions, simplified_path)

    assert detailed_path.exists()
    assert simplified_path.exists()
    assert detailed_path.stat().st_size > 500
    assert simplified_path.stat().st_size > 500


def test_06_non_destructive_parallel_execution():
    """Test 6: Layout intelligence operates purely as an analytical layer without altering frozen OCR pipeline."""
    doc13_path = backend_dir / "uploads" / "handwritten" / "13" / "processed" / "page_001.png"

    # Analyze layout
    layout_res = analyze_page_layout(str(doc13_path))
    assert layout_res is not None

    # Run frozen OCR 3.5 pipeline directly and ensure identical contract
    ocr_res = transcribe_page_image(doc13_path)
    assert "recovered_text" in ocr_res
    assert "lines" in ocr_res
    assert len(ocr_res["lines"]) == 20  # Frozen baseline line count preserved exactly


def test_07_table_detection_logic():
    """Test 7: Tabular grid detection requires intersecting horizontal and internal vertical column dividers."""
    # Synthetic grid table: 3 horizontal rules, 3 vertical rules
    table_img = np.ones((600, 800, 3), dtype=np.uint8) * 255
    # Draw horizontal table lines
    cv2.line(table_img, (150, 150), (650, 150), (0, 0, 0), 2)
    cv2.line(table_img, (150, 250), (650, 250), (0, 0, 0), 2)
    cv2.line(table_img, (150, 350), (650, 350), (0, 0, 0), 2)
    # Draw vertical column dividers
    cv2.line(table_img, (150, 150), (150, 350), (0, 0, 0), 2)
    cv2.line(table_img, (400, 150), (400, 350), (0, 0, 0), 2)
    cv2.line(table_img, (650, 150), (650, 350), (0, 0, 0), 2)

    res = analyze_page_layout(table_img)
    assert res["has_tables"] is True
    assert res["counts_by_type"].get(REGION_TABLE, 0) >= 1


def test_08_formula_protection_no_false_positives():
    """Test 8: Normal handwritten poetry/notes do not produce false positive formula regions."""
    doc10_path = backend_dir / "uploads" / "handwritten" / "10" / "processed" / "page_001.png"
    res10 = analyze_page_layout(str(doc10_path))
    assert res10["has_formulas"] is False
    assert res10["counts_by_type"].get(REGION_FORMULA, 0) == 0

    doc12_path = backend_dir / "uploads" / "handwritten" / "12" / "processed" / "page_001.png"
    res12 = analyze_page_layout(str(doc12_path))
    assert res12["has_formulas"] is False
    assert res12["counts_by_type"].get(REGION_FORMULA, 0) == 0


def test_09_bounding_box_clamping():
    """Test 9: All detected region bounding boxes and polygons are clamped to valid image coordinate bounds."""
    for p_num in range(1, 4):
        p_path = backend_dir / "uploads" / "handwritten" / "12" / "processed" / f"page_00{p_num}.png"
        img = cv2.imread(str(p_path))
        h, w = img.shape[:2]
        res = analyze_page_layout(img)

        for reg in res["regions"]:
            x, y, bw, bh = reg["bbox"]
            assert x >= 0 and y >= 0, f"Negative coordinate in bbox: {reg['bbox']}"
            assert x + bw <= w, f"Region exceeds width {w}: {reg['bbox']}"
            assert y + bh <= h, f"Region exceeds height {h}: {reg['bbox']}"
            assert bw > 0 and bh > 0, f"Empty region dimension: {reg['bbox']}"

            for pt in reg["polygon"]:
                assert 0 <= pt[0] <= w
                assert 0 <= pt[1] <= h


def test_10_cpu_execution_time_latency():
    """Test 10: Execution latency on CPU remains well under 500ms per standard page."""
    doc13_path = backend_dir / "uploads" / "handwritten" / "13" / "processed" / "page_001.png"
    t0 = time.time()
    res = analyze_page_layout(str(doc13_path))
    elapsed_ms = (time.time() - t0) * 1000

    assert elapsed_ms < 500.0, f"CPU latency {elapsed_ms:.1f}ms exceeds 500ms threshold"
    assert res["execution_time_ms"] < 500.0


if __name__ == "__main__":
    tests = [
        test_01_blank_page_negative_control,
        test_02_doc13_diagram_detection,
        test_03_heading_vs_text_differentiation,
        test_04_region_data_model_integrity,
        test_05_visualizer_rendering,
        test_06_non_destructive_parallel_execution,
        test_07_table_detection_logic,
        test_08_formula_protection_no_false_positives,
        test_09_bounding_box_clamping,
        test_10_cpu_execution_time_latency
    ]

    print(f"Running {len(tests)} Layout Intelligence 4.0 tests...\n")
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f" PASS: {t.__name__}")
            passed += 1
        except Exception as e:
            print(f" FAIL: {t.__name__} - {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\nCompleted: {passed} passed, {failed} failed.")
    if failed > 0:
        sys.exit(1)
    print("ALL LAYOUT INTELLIGENCE TESTS PASSED!")
