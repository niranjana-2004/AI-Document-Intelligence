import cv2
import numpy as np
from pathlib import Path

def inspect_page_features(img_path: str):
    p = Path(img_path)
    if not p.exists():
        print(f"File not found: {p}")
        return
    img = cv2.imread(str(p))
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Check ink std dev
    std = float(np.std(gray))
    ink_ratio = np.sum(thresh > 0) / (h * w)
    print(f"\n=== {p.name} ({w}x{h}) ===")
    print(f"Grayscale std: {std:.2f}, ink ratio: {ink_ratio*100:.3f}%")
    if std < 3.0 or ink_ratio < 0.0005:
        print("-> BLANK PAGE")
        return

    # Morphological long horizontal and vertical lines
    len_h = max(40, int(w * 0.06))
    k_h = cv2.getStructuringElement(cv2.MORPH_RECT, (len_h, 1))
    h_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, k_h)

    len_v = max(30, int(h * 0.03))
    k_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, len_v))
    v_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, k_v)

    combined_lines = cv2.add(h_lines, v_lines)
    h_ink = np.sum(h_lines > 0)
    v_ink = np.sum(v_lines > 0)
    print(f"Horizontal line ink: {h_ink} ({h_ink/(h*w)*100:.3f}%), Vertical line ink: {v_ink} ({v_ink/(h*w)*100:.3f}%)")

    # Box contours (contours of combined lines or closed shapes)
    k_close = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    closed_lines = cv2.morphologyEx(combined_lines, cv2.MORPH_CLOSE, k_close)
    cnts, _ = cv2.findContours(closed_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in cnts:
        bx, by, bw, bh = cv2.boundingRect(c)
        if bw > w * 0.08 and bh > h * 0.02:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.04 * peri, True)
            boxes.append((bx, by, bw, bh, len(approx)))
    print(f"Structural line/box components: {len(boxes)}")
    for b in boxes[:10]:
        print(f"  Box: bbox=[x={b[0]}, y={b[1]}, w={b[2]}, h={b[3]}], vertices={b[4]}")

inspect_page_features("backend/uploads/handwritten/13/processed/page_001.png")
inspect_page_features("backend/uploads/handwritten/12/processed/page_001.png")
inspect_page_features("backend/uploads/handwritten/10/processed/page_001.png")
inspect_page_features("uploads/handwritten/4/processed/page_001.png")

