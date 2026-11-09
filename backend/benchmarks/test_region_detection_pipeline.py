import cv2
import numpy as np
from pathlib import Path
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

def detect_page_regions(img_path: str):
    p = Path(img_path)
    if not p.exists():
        p = Path("backend") / img_path
    if not p.exists():
        p = Path("D:/AI-Document-Intelligence") / img_path
    img = cv2.imread(str(p))
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    std = float(np.std(gray))
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ink_ratio = np.sum(thresh > 0) / (h * w)

    if std < 3.0 or ink_ratio < 0.0005:
        return [{"type": "background", "bbox": (0, 0, w, h), "conf": 1.0}]

    # 1. Ruling line suppression
    k_ruling = cv2.getStructuringElement(cv2.MORPH_RECT, (max(50, int(w * 0.40)), 1))
    ruling = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, k_ruling)
    clean_thresh = cv2.subtract(thresh, ruling)

    # 2. Suppress margin lines
    k_v_margin = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(60, int(h * 0.03))))
    v_margin = cv2.morphologyEx(clean_thresh, cv2.MORPH_OPEN, k_v_margin)
    margin_mask = np.zeros_like(thresh)
    margin_mask[:, :int(w * 0.12)] = v_margin[:, :int(w * 0.12)]
    margin_mask[:, int(w * 0.90):] = v_margin[:, int(w * 0.90):]
    clean_thresh = cv2.subtract(clean_thresh, cv2.dilate(margin_mask, np.ones((5, 5), np.uint8)))

    # 3. Detect flowchart / diagram boxes:
    # A diagram box has significant vertical edges AND horizontal edges inside the page body
    k_h = cv2.getStructuringElement(cv2.MORPH_RECT, (max(45, int(w * 0.045)), 2))
    h_lines = cv2.morphologyEx(clean_thresh, cv2.MORPH_OPEN, k_h)

    k_v = cv2.getStructuringElement(cv2.MORPH_RECT, (2, max(35, int(h * 0.02))))
    v_lines = cv2.morphologyEx(clean_thresh, cv2.MORPH_OPEN, k_v)

    combined_lines = cv2.add(h_lines, v_lines)
    k_close = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    closed = cv2.morphologyEx(combined_lines, cv2.MORPH_CLOSE, k_close)

    cnts, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    diagram_boxes = []
    for c in cnts:
        bx, by, bw, bh = cv2.boundingRect(c)
        if bw < max(80, int(w * 0.08)) or bh < 35:
            continue
        if bw > w * 0.95 and bh > h * 0.90:
            continue
        sub_h = h_lines[by:by+bh, bx:bx+bw]
        sub_v = v_lines[by:by+bh, bx:bx+bw]
        if np.sum(sub_h > 0) > 40 and np.sum(sub_v > 0) > 30:
            diagram_boxes.append((bx, by, bw, bh))

    # Also detect vertical diagram region from line heights and spacing
    # In Document 13, the diagram spans from y=940 to y=1800
    # Let's check if diagram boxes exist
    regions = []
    non_text_mask = np.zeros_like(thresh)

    if diagram_boxes:
        # Merge diagram boxes into diagram region
        min_y = min(b[1] for b in diagram_boxes)
        max_y = max(b[1] + b[3] for b in diagram_boxes)
        min_x = min(b[0] for b in diagram_boxes)
        max_x = max(b[0] + b[2] for b in diagram_boxes)

        # Pad slightly
        pad_y = 20
        diag_y1 = max(0, min_y - pad_y)
        diag_y2 = min(h, max_y + pad_y)
        diag_x1 = max(0, min_x - 15)
        diag_x2 = min(w, max_x + 15)

        diag_w = diag_x2 - diag_x1
        diag_h = diag_y2 - diag_y1

        regions.append({
            "type": "diagram",
            "bbox": (diag_x1, diag_y1, diag_w, diag_h),
            "conf": 0.90,
            "sub_boxes": diagram_boxes
        })
        cv2.rectangle(non_text_mask, (0, diag_y1), (w, diag_y2), 255, -1)

    # 4. Text regions in remaining areas
    text_ink = cv2.subtract(clean_thresh, non_text_mask)
    row_ink = np.sum(text_ink > 0, axis=1).astype(np.float32)
    smoothed = gaussian_filter1d(row_ink, sigma=8.0)
    peaks, _ = find_peaks(smoothed, distance=20, prominence=15.0)

    # Split page vertically where non_text_mask is 0
    # Find contiguous vertical bands of text
    active_rows = np.where(smoothed > 25.0)[0]
    if len(active_rows) > 0:
        # Cluster active rows into text blocks
        text_clusters = []
        c_start = active_rows[0]
        c_prev = active_rows[0]
        for r in active_rows[1:]:
            if r - c_prev > 45:
                text_clusters.append((c_start, c_prev))
                c_start = r
            c_prev = r
        text_clusters.append((c_start, c_prev))

        for tc in text_clusters:
            y1 = max(0, tc[0] - 15)
            y2 = min(h, tc[1] + 20)
            bh = y2 - y1
            if bh < 25:
                continue
            # Find horizontal width
            sub_ink = text_ink[y1:y2, :]
            cols = np.where(np.sum(sub_ink > 0, axis=0) > 3)[0]
            if len(cols) > 0:
                x1 = max(0, int(cols[0]) - 10)
                x2 = min(w, int(cols[-1]) + 10)
                bw = x2 - x1
            else:
                x1, bw = 0, w

            # Heading vs Paragraph:
            # Top 15% of page with small height (< 100px) is heading
            is_top = (y1 / float(h)) < 0.15
            is_heading = is_top and bh < 120
            rtype = "heading" if is_heading else "text"

            regions.append({
                "type": rtype,
                "bbox": (x1, y1, bw, bh),
                "conf": 0.92
            })

    # Sort top to bottom
    regions.sort(key=lambda r: r["bbox"][1])
    return regions

print("=== Doc 13 Regions ===")
r_13 = detect_page_regions("backend/uploads/handwritten/13/processed/page_001.png")
for r in r_13:
    print(f"[{r['type'].upper()}] bbox={r['bbox']}, conf={r['conf']}")

print("\n=== Doc 12 P1 Regions ===")
r_12 = detect_page_regions("backend/uploads/handwritten/12/processed/page_001.png")
for r in r_12:
    print(f"[{r['type'].upper()}] bbox={r['bbox']}, conf={r['conf']}")

print("\n=== Doc 10 Regions ===")
r_10 = detect_page_regions("backend/uploads/handwritten/10/processed/page_001.png")
for r in r_10:
    print(f"[{r['type'].upper()}] bbox={r['bbox']}, conf={r['conf']}")

print("\n=== Root 4 (Blank) Regions ===")
r_4 = detect_page_regions("uploads/handwritten/4/processed/page_001.png")
for r in r_4:
    print(f"[{r['type'].upper()}] bbox={r['bbox']}, conf={r['conf']}")

