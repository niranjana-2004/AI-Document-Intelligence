import cv2
import numpy as np
from pathlib import Path

def detect_closed_boxes(img_path: str):
    p = Path(img_path)
    if not p.exists():
        p = Path("backend") / img_path
    if not p.exists():
        print(f"Not found: {img_path}")
        return []

    img = cv2.imread(str(p))
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # 1. Suppress vertical page margin lines (x < 0.12*w and x > 0.90*w)
    k_v_margin = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 80))
    v_margin = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, k_v_margin)
    margin_mask = np.zeros_like(thresh)
    margin_mask[:, :int(w * 0.12)] = v_margin[:, :int(w * 0.12)]
    margin_mask[:, int(w * 0.90):] = v_margin[:, int(w * 0.90):]
    clean_thresh = cv2.subtract(thresh, cv2.dilate(margin_mask, np.ones((5, 5), np.uint8)))

    # 2. Suppress horizontal notebook ruling lines (> 40% width)
    k_ruling = cv2.getStructuringElement(cv2.MORPH_RECT, (int(w * 0.35), 1))
    ruling = cv2.morphologyEx(clean_thresh, cv2.MORPH_OPEN, k_ruling)
    clean_thresh = cv2.subtract(clean_thresh, ruling)

    # 3. Detect horizontal borders (length >= 80px) and vertical borders (length >= 45px)
    k_h = cv2.getStructuringElement(cv2.MORPH_RECT, (max(50, int(w * 0.05)), 2))
    h_lines = cv2.morphologyEx(clean_thresh, cv2.MORPH_OPEN, k_h)

    k_v = cv2.getStructuringElement(cv2.MORPH_RECT, (2, max(40, int(h * 0.025))))
    v_lines = cv2.morphologyEx(clean_thresh, cv2.MORPH_OPEN, k_v)

    combined = cv2.add(h_lines, v_lines)
    # Dilate and close to connect corners
    k_close = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    closed = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, k_close)

    cnts, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in cnts:
        x, y, bw, bh = cv2.boundingRect(c)
        if bw < max(100, int(w * 0.08)) or bh < max(40, int(h * 0.02)):
            continue
        if bw > w * 0.95 and bh > h * 0.90:
            continue

        # Check for top, bottom, left, right border presence
        sub_h = h_lines[y:y+bh, x:x+bw]
        sub_v = v_lines[y:y+bh, x:x+bw]

        top_h = np.sum(sub_h[:int(bh*0.35), :] > 0)
        bot_h = np.sum(sub_h[int(bh*0.65):, :] > 0)
        left_v = np.sum(sub_v[:, :int(bw*0.35)] > 0)
        right_v = np.sum(sub_v[:, int(bw*0.65):] > 0)

        # A real box has horizontal support (top or bottom) and vertical support (left or right)
        has_h = (top_h > 30 or bot_h > 30)
        has_v = (left_v > 20 or right_v > 20)

        if has_h and has_v:
            boxes.append((x, y, bw, bh, top_h, bot_h, left_v, right_v))

    print(f"\n{p.name} -> Detected {len(boxes)} diagram boxes:")
    for b in boxes:
        print(f"  Box bbox=[x={b[0]}, y={b[1]}, w={b[2]}, h={b[3]}], top_H={b[4]}, bot_H={b[5]}, left_V={b[6]}, right_V={b[7]}")
    return boxes

detect_closed_boxes("backend/uploads/handwritten/13/processed/page_001.png")
detect_closed_boxes("backend/uploads/handwritten/12/processed/page_001.png")
detect_closed_boxes("backend/uploads/handwritten/10/processed/page_001.png")
detect_closed_boxes("uploads/handwritten/1/processed/page_001.png")
detect_closed_boxes("uploads/handwritten/4/processed/page_001.png")

