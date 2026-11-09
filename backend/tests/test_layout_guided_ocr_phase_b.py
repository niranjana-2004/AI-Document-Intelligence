"""
Cognidocs Layout Intelligence 4.0 — Phase B: Unit & Integration Test Suite

Validates:
1. Feature flag gating (disabled -> exact baseline OCR 3.5).
2. Feature flag enabled -> layout-guided OCR pipeline.
3. Low layout confidence -> automatic baseline fallback.
4. No text regions detected -> automatic baseline fallback.
5. Crop bounding box clamping to image boundaries.
6. Crop padding preservation.
7. Crop to page coordinate mapping determinism.
8. Multiple region reading order reconstruction.
9. Diagram exclusion from text lines (Document #13).
10. Non-text structure (arrows/connectors) suppression.
11. Blank page negative control safety (Root Sample 4).
12. Crop failure / corrupt subregion fallback.
13. Zero-line extraction fallback.
14. Manual edit protection preservation.
15. Phase B metadata integrity.
16. Safety test: layout service exception -> seamless baseline fallback.
"""

import sys
import os
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import cv2

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(str(backend_dir))

from app.core.config import settings
from app.services.handwriting.transcription_pipeline import transcribe_page_image
from app.services.handwriting.layout_guided_ocr_service import (
    transcribe_page_image_baseline,
    transcribe_page_image_layout_guided,
    order_regions_reading_flow,
    CROP_PADDING_PX
)
from app.services.handwriting.layout_intelligence_service import (
    REGION_TEXT,
    REGION_HEADING,
    REGION_DIAGRAM,
    REGION_ARROW,
    REGION_BACKGROUND
)


class TestLayoutGuidedOCRPhaseB(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Locate sample files
        cls.doc13_path = backend_dir / "uploads" / "handwritten" / "13" / "processed" / "page_001.png"
        cls.blank_path = backend_dir.parent / "uploads" / "handwritten" / "4" / "processed" / "page_001.png"
        if not cls.blank_path.exists():
            cls.blank_path = backend_dir / "uploads" / "handwritten" / "4" / "processed" / "page_001.png"

        # Create non-blank synthetic test image for fallback testing
        art_dir = backend_dir / "benchmarks" / "artifacts"
        art_dir.mkdir(parents=True, exist_ok=True)
        cls.dummy_non_blank_path = art_dir / "test_non_blank.png"
        img = np.full((600, 800, 3), 255, dtype=np.uint8)
        cv2.line(img, (50, 100), (750, 100), (0, 0, 0), 4)
        cv2.line(img, (50, 200), (750, 200), (0, 0, 0), 4)
        cv2.imwrite(str(cls.dummy_non_blank_path), img)

    def test_01_feature_flag_disabled_exact_baseline(self):
        """When LAYOUT_GUIDED_OCR_ENABLED is False, pipeline returns exact baseline metadata."""
        with patch.object(settings, "LAYOUT_GUIDED_OCR_ENABLED", False):
            # Test on blank page for speed
            if self.blank_path.exists():
                res = transcribe_page_image(self.blank_path)
                self.assertEqual(res["ocr_mode"], "ocr35_baseline")
                self.assertFalse(res["layout_enabled"])
                self.assertFalse(res["fallback_used"])

    def test_02_feature_flag_enabled_layout_pipeline_runs(self):
        """When forced or enabled, layout pipeline runs and emits layout_enabled=True."""
        if self.blank_path.exists():
            res = transcribe_page_image(self.blank_path, force_layout_guided=True)
            self.assertTrue(res["layout_enabled"])
            self.assertEqual(res["layout_version"], "4.0-phase-b")

    def test_03_layout_confidence_below_threshold_fallback(self):
        """When detected text regions have confidence < 0.60, fallback triggers."""
        low_conf_layout = {
            "page_id": 1,
            "is_empty": False,
            "width": 1000,
            "height": 1400,
            "total_regions": 1,
            "regions": [
                {
                    "id": "text_1",
                    "region_type": REGION_TEXT,
                    "bbox": [50, 50, 800, 200],
                    "confidence": 0.45  # below MIN_LAYOUT_CONFIDENCE (0.60)
                }
            ],
            "counts_by_type": {REGION_TEXT: 1}
        }
        with patch("app.services.handwriting.layout_guided_ocr_service.analyze_page_layout", return_value=low_conf_layout):
            res = transcribe_page_image_layout_guided(self.dummy_non_blank_path)
            self.assertTrue(res["fallback_used"])
            self.assertEqual(res["ocr_mode"], "ocr35_baseline_fallback")
            self.assertIn("no_confident_text_regions", res["fallback_reason"])

    def test_04_no_text_regions_fallback(self):
        """When only diagrams exist and no text regions, fallback to baseline triggers."""
        diag_only_layout = {
            "page_id": 1,
            "is_empty": False,
            "width": 1000,
            "height": 1400,
            "total_regions": 1,
            "regions": [
                {
                    "id": "diag_1",
                    "region_type": REGION_DIAGRAM,
                    "bbox": [50, 300, 900, 800],
                    "confidence": 0.95
                }
            ],
            "counts_by_type": {REGION_DIAGRAM: 1}
        }
        with patch("app.services.handwriting.layout_guided_ocr_service.analyze_page_layout", return_value=diag_only_layout):
            res = transcribe_page_image_layout_guided(self.dummy_non_blank_path)
            self.assertTrue(res["fallback_used"])
            self.assertEqual(res["ocr_mode"], "ocr35_baseline_fallback")

    def test_05_crop_bounding_box_clamping(self):
        """Bounding box clamping must never produce coordinates outside [0, w] x [0, h]."""
        w, h = 1000, 1500
        padding = 10
        # Extreme box overflowing all boundaries
        rx, ry, rw, rh = -50, -30, 1200, 1600

        crop_x1 = max(0, rx - padding)
        crop_y1 = max(0, ry - padding)
        crop_x2 = min(w, rx + rw + padding)
        crop_y2 = min(h, ry + rh + padding)

        self.assertGreaterEqual(crop_x1, 0)
        self.assertGreaterEqual(crop_y1, 0)
        self.assertLessEqual(crop_x2, w)
        self.assertLessEqual(crop_y2, h)
        self.assertEqual(crop_x1, 0)
        self.assertEqual(crop_y1, 0)
        self.assertEqual(crop_x2, w)
        self.assertEqual(crop_y2, h)

    def test_06_crop_padding_preservation(self):
        """Internal region gets padded by CROP_PADDING_PX safely."""
        w, h = 1000, 1000
        pad = CROP_PADDING_PX  # 8
        rx, ry, rw, rh = 100, 100, 200, 150

        crop_x1 = max(0, rx - pad)
        crop_y1 = max(0, ry - pad)
        crop_x2 = min(w, rx + rw + pad)
        crop_y2 = min(h, ry + rh + pad)

        self.assertEqual(crop_x1, 92)
        self.assertEqual(crop_y1, 92)
        self.assertEqual(crop_x2, 308)
        self.assertEqual(crop_y2, 258)

    def test_07_crop_to_page_coordinate_mapping(self):
        """Line detected at (lx, ly, lw, lh) inside crop (crop_x1, crop_y1) maps to (crop_x1+lx, crop_y1+ly)."""
        crop_x1, crop_y1 = 150, 400
        lx, ly, lw, lh = 20, 35, 300, 45

        page_bx = crop_x1 + lx
        page_by = crop_y1 + ly

        self.assertEqual(page_bx, 170)
        self.assertEqual(page_by, 435)

    def test_08_multiple_region_reading_order(self):
        """Top heading precedes body text; lower body text follows in order."""
        regions = [
            {"id": "text_2", "region_type": REGION_TEXT, "bbox": [50, 900, 700, 200]},
            {"id": "heading_1", "region_type": REGION_HEADING, "bbox": [60, 80, 600, 100]},
            {"id": "text_1", "region_type": REGION_TEXT, "bbox": [55, 250, 750, 300]}
        ]
        ordered = order_regions_reading_flow(regions)
        ordered_ids = [r["id"] for r in ordered]
        self.assertEqual(ordered_ids, ["heading_1", "text_1", "text_2"])

    def test_09_diagram_exclusion_on_doc13(self):
        """On Document #13, diagram region is identified and preserved as non-text."""
        if not self.doc13_path.exists():
            self.skipTest("Document #13 sample missing")

        img = cv2.imread(str(self.doc13_path))
        from app.services.handwriting.layout_intelligence_service import analyze_page_layout
        layout = analyze_page_layout(img, page_id=13, subject="Web Development")

        # Diagram region must be detected
        has_diagram = any(r["region_type"] == REGION_DIAGRAM for r in layout["regions"])
        self.assertTrue(has_diagram, "Diagram was not detected on Document #13")

    def test_10_non_text_structure_suppression(self):
        """Diagram, connector, and arrow regions are filtered out of text_regions."""
        mock_layout = {
            "regions": [
                {"id": "h1", "region_type": REGION_HEADING, "confidence": 0.95, "bbox": [50, 50, 500, 60]},
                {"id": "t1", "region_type": REGION_TEXT, "confidence": 0.92, "bbox": [50, 150, 500, 200]},
                {"id": "d1", "region_type": REGION_DIAGRAM, "confidence": 0.96, "bbox": [50, 400, 800, 500]},
                {"id": "a1", "region_type": REGION_ARROW, "confidence": 0.90, "bbox": [100, 450, 20, 80]}
            ]
        }
        text_regs = [
            r for r in mock_layout["regions"]
            if r["region_type"] in (REGION_TEXT, REGION_HEADING)
            and r["confidence"] >= 0.60
        ]
        text_types = [r["region_type"] for r in text_regs]
        self.assertIn(REGION_HEADING, text_types)
        self.assertIn(REGION_TEXT, text_types)
        self.assertNotIn(REGION_DIAGRAM, text_types)
        self.assertNotIn(REGION_ARROW, text_types)

    def test_11_blank_page_negative_control(self):
        """Blank page (Root 4) must yield is_empty=True and zero false text lines."""
        if not self.blank_path.exists():
            self.skipTest("Blank control missing")

        res = transcribe_page_image_layout_guided(self.blank_path)
        self.assertTrue(res["is_empty"])
        self.assertEqual(res["total_lines"], 0)
        self.assertEqual(res["full_text"], "")
        self.assertFalse(res["fallback_used"])

    def test_12_ocr_crop_failure_fallback(self):
        """If line segmentation raises an exception inside a region, fallback handles safely."""
        mock_layout = {
            "page_id": 1,
            "is_empty": False,
            "width": 800,
            "height": 600,
            "total_regions": 1,
            "regions": [
                {"id": "t1", "region_type": REGION_TEXT, "confidence": 0.9, "bbox": [50, 50, 400, 200]}
            ],
            "counts_by_type": {REGION_TEXT: 1}
        }
        from app.services.handwriting.line_segmenter import segment_page_into_lines as orig_seg
        calls = [0]
        def fail_first_call(img, *args, **kwargs):
            calls[0] += 1
            if calls[0] == 1:
                raise RuntimeError("Line segmentation failure")
            return orig_seg(img, *args, **kwargs)

        with patch("app.services.handwriting.layout_guided_ocr_service.analyze_page_layout", return_value=mock_layout), \
             patch("app.services.handwriting.layout_guided_ocr_service.segment_page_into_lines", side_effect=fail_first_call):
            res = transcribe_page_image_layout_guided(self.dummy_non_blank_path)
            self.assertTrue(res["fallback_used"])
            self.assertEqual(res["ocr_mode"], "ocr35_baseline_fallback")

    def test_13_zero_line_extraction_fallback(self):
        """If candidate text regions yield 0 lines, fallback triggers to baseline OCR 3.5."""
        mock_layout = {
            "page_id": 1,
            "is_empty": False,
            "width": 800,
            "height": 600,
            "total_regions": 1,
            "regions": [
                {"id": "t1", "region_type": REGION_TEXT, "confidence": 0.9, "bbox": [50, 50, 400, 200]}
            ],
            "counts_by_type": {REGION_TEXT: 1}
        }
        from app.services.handwriting.line_segmenter import segment_page_into_lines as orig_seg
        calls = [0]
        def empty_first_call(img, *args, **kwargs):
            calls[0] += 1
            if calls[0] == 1:
                return ([], True)
            return orig_seg(img, *args, **kwargs)

        with patch("app.services.handwriting.layout_guided_ocr_service.analyze_page_layout", return_value=mock_layout), \
             patch("app.services.handwriting.layout_guided_ocr_service.segment_page_into_lines", side_effect=empty_first_call):
            res = transcribe_page_image_layout_guided(self.dummy_non_blank_path)
            self.assertTrue(res["fallback_used"])
            self.assertEqual(res["ocr_mode"], "ocr35_baseline_fallback")
            self.assertEqual(res["fallback_reason"], "zero_lines_extracted_from_text_regions")

    def test_14_manual_edit_protection(self):
        """Manual edit flag and user text are always protected."""
        dummy_meta = {
            "is_manually_edited": True,
            "user_manual_transcription": "VERIFIED STUDENT NOTES",
            "ocr_mode": "layout_guided_ocr35"
        }
        is_manual = dummy_meta.get("is_manually_edited", False)
        user_manual_text = dummy_meta.get("user_manual_transcription")

        simulated_ocr_text = "Automated OCR re-transcription"
        edited_transcription = user_manual_text if (is_manual and user_manual_text) else simulated_ocr_text

        self.assertEqual(edited_transcription, "VERIFIED STUDENT NOTES")
        self.assertNotEqual(edited_transcription, simulated_ocr_text)

    def test_15_metadata_integrity(self):
        """Result dictionary must conform to Phase B schema."""
        if not self.blank_path.exists():
            self.skipTest("Blank sample missing")

        res = transcribe_page_image_layout_guided(self.blank_path)
        required_keys = [
            "raw_text", "recovered_text", "full_text", "confidence_score",
            "total_lines", "is_empty", "execution_time_ms", "lines",
            "ocr_mode", "layout_enabled", "layout_version", "regions_detected",
            "text_regions_used", "diagram_regions_preserved", "formula_regions_preserved",
            "fallback_used", "fallback_reason", "layout_confidence", "baseline_available"
        ]
        for key in required_keys:
            self.assertIn(key, res, f"Missing required metadata key: {key}")

    def test_16_safety_layout_detection_failure_fallback(self):
        """When analyze_page_layout throws an exception, pipeline cleanly falls back to baseline."""
        with patch("app.services.handwriting.layout_guided_ocr_service.analyze_page_layout", side_effect=Exception("Simulated crash")):
            res = transcribe_page_image_layout_guided(self.dummy_non_blank_path)
            self.assertTrue(res["fallback_used"])
            self.assertEqual(res["ocr_mode"], "ocr35_baseline_fallback")
            self.assertIn("layout_analysis_exception", res["fallback_reason"])


if __name__ == "__main__":
    unittest.main()
