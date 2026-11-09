import cv2
import numpy as np
from pathlib import Path
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

def analyze_layout_robust(img_path: str):
    p = Path(img_path)
    if not p.exists():
        p = Path("backend") / img_path
    if not p.exists():
        p = Path("D:/AI-Document-Intelligence") / img_path
    if not p.exists():
        print(f"File not found: {img_path}")
        return

    img = cv2.imread(str(p))
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    std = float(np.std(gray))
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ink_ratio = np.sum(thresh > 0) / (h * w)

    print(f"\n=======================================================")
    print(f"Sample: {p.name} ({w}x{h}) | std: {std:.2f} | ink: {ink_ratio*100:.3f}%")
    if std < 3.0 or ink_ratio < 0.0005:
        print("-> Result: BLANK PAGE (Empty negative control)")
        return

    # 1. Ruling line suppression (thin horizontal lines spanning > 45% width)
    line_len = max(60, int(w * 0.45))
    k_ruling = cv2.getStructuringElement(cv2.MORPH_RECT, (line_len, 1))
    ruling = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, k_ruling)
    clean_thresh = cv2.subtract(thresh, ruling)

    # 2. Suppress vertical page margin lines (x < 0.12*w or x > 0.90*w)
    k_v_margin = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(60, int(h * 0.03))))
    v_margin = cv2.morphologyEx(clean_thresh, cv2.MORPH_OPEN, k_v_margin)
    margin_mask = np.zeros_like(thresh)
    margin_mask[:, :int(w * 0.12)] = v_margin[:, :int(w * 0.12)]
    margin_mask[:, int(w * 0.90):] = v_margin[:, int(w * 0.90):]
    clean_thresh = cv2.subtract(clean_thresh, cv2.dilate(margin_mask, np.ones((5, 5), np.uint8)))

    # 3. Detect 2D Diagram Boxes & Flowcharts
    # A diagram box has BOTH horizontal borders (>= 80px) and vertical borders (>= 35px)
    k_h = cv2.getStructuringElement(cv2.MORPH_RECT, (max(50, int(w * 0.045)), 2))
    h_lines = cv2.morphologyEx(clean_thresh, cv2.MORPH_OPEN, k_h)

    k_v = cv2.getStructuringElement(cv2.MORPH_RECT, (2, max(35, int(h * 0.02))))
    v_lines = cv2.morphologyEx(clean_thresh, cv2.MORPH_OPEN, k_v)

    combined_lines = cv2.add(h_lines, v_lines)
    k_close = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    closed = cv2.morphologyEx(combined_lines, cv2.MORPH_CLOSE, k_close)

    cnts, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    diagram_boxes = []
    for c in cnts:
        x, y, bw, bh = cv2.boundingRect(c)
        if bw < max(80, int(w * 0.08)) or bh < max(35, int(h * 0.02)):
            continue
        if bw > w * 0.95 and bh > h * 0.90:
            continue

        sub_h = h_lines[y:y+bh, x:x+bw]
        sub_v = v_lines[y:y+bh, x:x+bw]
        h_pix = np.sum(sub_h > 0)
        v_pix = np.sum(sub_v > 0)

        # Must have significant horizontal and vertical support
        if h_pix > 50 and v_pix > 35:
            # Check internal text density (diagram box is hollow or contains labels)
            area = bw * bh
            sub_thresh = clean_thresh[y:y+bh, x:x+bw]
            ink_density = np.sum(sub_thresh > 0) / max(1, area)
            if ink_density < 0.35:
                diagram_boxes.append((x, y, bw, bh))

    print(f"Detected {len(diagram_boxes)} diagram boxes:")
    for b in diagram_boxes:
        print(f"  Box: y={b[1]}..{b[1]+b[3]}, x={b[0]}..{b[0]+b[2]}")

    # 4. Check for Mathematical Formulas
    # Fraction bars: isolated horizontal bar of length 25..120px with whitespace left and right
    k_frac = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1))
    frac_bars = cv2.morphologyEx(clean_thresh, cv2.MORPH_OPEN, k_frac)
    cnts_frac, _ = cv2.findContours(frac_bars, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    formula_regions = []
    for c in cnts_frac:
        x, y, bw, bh = cv2.boundingRect(c)
        if 25 <= bw <= int(w * 0.12) and bh <= 4:
            # Check for isolated whitespace to left and right
            x_left = max(0, x - 15)
            x_right = min(w, x + bw + 15)
            pad_left_ink = np.sum(clean_thresh[y:y+bh, x_left:x] > 0)
            pad_right_ink = np.sum(clean_thresh[y:y+bh, x+bw:x_right] > 0)

            # Check ink above and below
            y_above = max(0, y - int(bw * 0.6))
            y_below = min(h, y + bh + int(bw * 0.6))
            ink_above = np.sum(clean_thresh[y_above:y, x:x+bw] > 0)
            ink_below = np.sum(clean_thresh[y+bh:y_below, x:x+bw] > 0)

            if pad_left_ink == 0 and pad_right_ink == 0 and ink_above > 10 and ink_below > 10:
                formula_regions.append((x, y_above, bw, y_below - y_above))

    print(f"Detected {len(formula_regions)} mathematical formula regions:")
    for f in formula_regions:
        print(f"  Formula: y={f[1]}..{f[1]+f[3]}, x={f[0]}..{f[0]+f[2]}")

analyze_layout_robust("backend/uploads/handwritten/13/processed/page_001.png")
analyze_layout_robust("backend/uploads/handwritten/12/processed/page_001.png")
analyze_layout_robust("backend/uploads/handwritten/10/processed/page_001.png")
analyze_layout_robust("uploads/handwritten/1/processed/page_001.png")
analyze_layout_robust("uploads/handwritten/3/processed/page_001.png")
analyze_layout_robust("uploads/handwritten/4/processed/page_001.png")

