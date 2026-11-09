import cv2
import numpy as np
from pathlib import Path

def test_refined_detection(img_path: str):
    p = Path(img_path)
    if not p.exists():
        p = Path("backend") / img_path
    if not p.exists():
        print(f"Not found: {img_path}")
        return

    img = cv2.imread(str(p))
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    print(f"\n--- Testing on {p.name} ({w}x{h}) ---")

    # 1. Ruling line suppression (thin horizontal lines spanning > 40% width)
    line_len = max(50, int(w * 0.40))
    k_ruling = cv2.getStructuringElement(cv2.MORPH_RECT, (line_len, 1))
    ruling_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, k_ruling)
    clean_thresh = cv2.subtract(thresh, ruling_lines)

    # 2. Box detection: Find rectangles with BOTH horizontal and vertical edges
    # Horizontal edges of length >= 60 px
    k_h = cv2.getStructuringElement(cv2.MORPH_RECT, (max(40, int(w * 0.05)), 2))
    h_edges = cv2.morphologyEx(clean_thresh, cv2.MORPH_OPEN, k_h)

    # Vertical edges of length >= 35 px
    k_v = cv2.getStructuringElement(cv2.MORPH_RECT, (2, max(30, int(h * 0.025))))
    v_edges = cv2.morphologyEx(clean_thresh, cv2.MORPH_OPEN, k_v)

    # Combine edges and close small corner gaps
    box_edges = cv2.add(h_edges, v_edges)
    k_close = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    closed = cv2.morphologyEx(box_edges, cv2.MORPH_CLOSE, k_close)

    cnts, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid_boxes = []
    for c in cnts:
        x, y, bw, bh = cv2.boundingRect(c)
        # Filter: Must not be entire page or ruling line
        if bw < w * 0.08 or bh < 30:
            continue
        if bw > w * 0.95 and bh > h * 0.90:
            continue
        # Crucial check: Must contain BOTH horizontal and vertical edge pixels
        sub_h = h_edges[y:y+bh, x:x+bw]
        sub_v = v_edges[y:y+bh, x:x+bw]
        h_pix = np.sum(sub_h > 0)
        v_pix = np.sum(sub_v > 0)
        if h_pix > 50 and v_pix > 30:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.04 * peri, True)
            valid_boxes.append((x, y, bw, bh, len(approx), h_pix, v_pix))

    print(f"Detected {len(valid_boxes)} real boxes:")
    for b in valid_boxes:
        print(f"  Box bbox=[x={b[0]}, y={b[1]}, w={b[2]}, h={b[3]}], vertices={b[4]}, H_ink={b[5]}, V_ink={b[6]}")

test_refined_detection("backend/uploads/handwritten/13/processed/page_001.png")
test_refined_detection("backend/uploads/handwritten/10/processed/page_001.png")
test_refined_detection("backend/uploads/handwritten/12/processed/page_001.png")

