import cv2
import numpy as np
from pathlib import Path

def test_four_borders(img_path: str):
    p = Path(img_path)
    if not p.exists():
        p = Path("backend") / img_path
    if not p.exists():
        p = Path("D:/AI-Document-Intelligence") / img_path
    img = cv2.imread(str(p))
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # 1. Notebook ruling suppression
    k_ruling = cv2.getStructuringElement(cv2.MORPH_RECT, (int(w * 0.40), 1))
    ruling = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, k_ruling)
    clean = cv2.subtract(thresh, ruling)

    # 2. Page margin lines suppression
    k_v_margin = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 80))
    v_margin = cv2.morphologyEx(clean, cv2.MORPH_OPEN, k_v_margin)
    margin_mask = np.zeros_like(thresh)
    margin_mask[:, :int(w * 0.10)] = v_margin[:, :int(w * 0.10)]
    margin_mask[:, int(w * 0.90):] = v_margin[:, int(w * 0.90):]
    margin_mask[:25, :] = 255
    margin_mask[-25:, :] = 255
    clean = cv2.subtract(clean, cv2.dilate(margin_mask, np.ones((5, 5), np.uint8)))

    # 3. Horizontal and vertical lines
    k_h = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 2))
    h_lines = cv2.morphologyEx(clean, cv2.MORPH_OPEN, k_h)

    k_v = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 30))
    v_lines = cv2.morphologyEx(clean, cv2.MORPH_OPEN, k_v)

    combined = cv2.add(h_lines, v_lines)
    k_close = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    closed = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, k_close)

    cnts, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in cnts:
        bx, by, bw, bh = cv2.boundingRect(c)
        if bw < 80 or bh < 35 or bw > w * 0.85:
            continue

        # Check for 4 borders:
        # Top 30% has horizontal line of length >= 50px
        top_h = h_lines[by:by+int(bh*0.35), bx:bx+bw]
        bot_h = h_lines[by+int(bh*0.65):by+bh, bx:bx+bw]
        left_v = v_lines[by:by+bh, bx:bx+int(bw*0.35)]
        right_v = v_lines[by:by+bh, bx+int(bw*0.65):bx+bw]

        top_len = np.max(np.sum(top_h > 0, axis=1)) if top_h.size > 0 else 0
        bot_len = np.max(np.sum(bot_h > 0, axis=1)) if bot_h.size > 0 else 0
        left_len = np.max(np.sum(left_v > 0, axis=0)) if left_v.size > 0 else 0
        right_len = np.max(np.sum(right_v > 0, axis=0)) if right_v.size > 0 else 0

        # Must have horizontal support top & bottom (or >= 60px) and vertical support left & right
        has_top_or_bot = (top_len >= 50 or bot_len >= 50)
        has_left_or_right = (left_len >= 25 or right_len >= 25)
        has_both_orientations = (top_len + bot_len >= 80) and (left_len + right_len >= 40)

        if has_both_orientations and (top_len > 0 or bot_len > 0) and (left_len > 0 or right_len > 0):
            boxes.append((bx, by, bw, bh, top_len, bot_len, left_len, right_len))

    print(f"\n{p.name} -> Detected {len(boxes)} boxes:")
    for b in boxes:
        print(f"  Box: y={b[1]}..{b[1]+b[3]}, x={b[0]}..{b[0]+b[2]} (top={b[4]}, bot={b[5]}, left={b[6]}, right={b[7]})")

test_four_borders("backend/uploads/handwritten/13/processed/page_001.png")
test_four_borders("backend/uploads/handwritten/12/processed/page_001.png")
test_four_borders("backend/uploads/handwritten/10/processed/page_001.png")
test_four_borders("uploads/handwritten/1/processed/page_001.png")

