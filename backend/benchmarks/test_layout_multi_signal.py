import cv2
import numpy as np
from pathlib import Path
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

def analyze_layout_multi_signal(img_path: str):
    p = Path(img_path)
    if not p.exists():
        p = Path("backend") / img_path
    if not p.exists():
        p = Path("D:/AI-Document-Intelligence") / img_path
    img = cv2.imread(str(p))
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    std_val = float(np.std(gray))
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ink_ratio = np.sum(thresh > 0) / (h * w)

    if std_val < 3.0 or ink_ratio < 0.0005:
        return [{"type": "background", "bbox": (0, 0, w, h), "confidence": 1.0}]

    # 1. Ruling line suppression
    line_len = max(30, int(w * 0.15))
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (line_len, 1))
    ruling_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_h)
    text_thresh = cv2.subtract(thresh, ruling_lines)

    # 2. Horizontal projection profile
    row_ink = np.sum(text_thresh > 0, axis=1).astype(np.float32)
    sigma = max(6.0, min(16.0, h / 140.0))
    smoothed = gaussian_filter1d(row_ink, sigma=sigma)

    min_dist = max(20, int(h * 0.018))
    active_ink = smoothed[smoothed > 0]
    prominence = max(18.0, float(np.percentile(active_ink, 20)) * 0.4) if len(active_ink) > 0 else 20.0
    peaks, _ = find_peaks(smoothed, distance=min_dist, prominence=prominence)
    min_peak_ink = max(30.0, 0.015 * w)
    valid_peaks = [p for p in peaks if smoothed[p] >= min_peak_ink]

    if not valid_peaks:
        return [{"type": "text", "bbox": (0, 0, w, h), "confidence": 0.80}]

    # Valleys between peaks
    search_top = max(0, int(valid_peaks[0] - (min_dist * 1.5)))
    first_ink = np.where(row_ink[search_top:valid_peaks[0]] > max(8, 0.004 * w))[0]
    top_y = max(0, search_top + first_ink[0] - 6) if len(first_ink) > 0 else max(0, int(valid_peaks[0] - (min_dist * 0.8)))

    valleys = [top_y]
    for i in range(len(valid_peaks) - 1):
        p1 = valid_peaks[i]
        p2 = valid_peaks[i + 1]
        valley_offset = int(np.argmin(smoothed[p1:p2]))
        valleys.append(p1 + valley_offset)

    search_bottom = min(h, int(valid_peaks[-1] + (min_dist * 1.5)))
    last_ink = np.where(row_ink[valid_peaks[-1]:search_bottom] > max(8, 0.004 * w))[0]
    bottom_y = min(h, valid_peaks[-1] + last_ink[-1] + 6) if len(last_ink) > 0 else min(h, int(valid_peaks[-1] + (min_dist * 0.8)))
    valleys.append(bottom_y)

    strips = []
    heights = []
    for i in range(len(valleys) - 1):
        y1 = max(0, valleys[i])
        y2 = min(h, valleys[i + 1])
        box_h = y2 - y1
        if box_h < 15:
            continue
        strip_thresh = thresh[y1:y2, :]
        cols = np.where(np.sum(strip_thresh > 0, axis=0) > 2)[0]
        if len(cols) > 0:
            x1 = max(0, int(cols[0]) - 8)
            x2 = min(w, int(cols[-1]) + 8)
        else:
            x1, x2 = 0, w
        box_w = max(10, x2 - x1)
        strips.append((x1, y1, box_w, box_h))
        heights.append(box_h)

    median_h = float(np.median(heights)) if heights else 50.0

    # 3. Analyze each strip for 2D diagram characteristics:
    # A diagram strip has:
    # - Abnormally large height (> 1.8x median height)
    # - Presence of closed box contours or vertical lines connecting across rows
    # - Low ink density / hollow interior (boxes)
    # - Or non-text aspect
    k_v = cv2.getStructuringElement(cv2.MORPH_RECT, (2, int(median_h * 0.6)))
    v_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, k_v)

    strip_types = []
    for (sx, sy, sw, sh) in strips:
        sub_v = v_lines[sy:sy+sh, sx:sx+sw]
        v_pix = np.sum(sub_v > 0)
        is_tall = sh > median_h * 1.8
        has_v_edges = v_pix > max(50, int(sh * 1.2))

        # Check if strip contains a 2D box or diagram element
        if (is_tall and has_v_edges) or (sh > median_h * 2.5):
            strip_types.append("diagram")
        elif (sy / float(h)) < 0.14 and sh <= median_h * 1.5:
            strip_types.append("heading")
        else:
            strip_types.append("text")

    # Group consecutive strips of the same category into cohesive regions
    regions = []
    curr_type = strip_types[0]
    curr_group = [strips[0]]

    for s, stype in zip(strips[1:], strip_types[1:]):
        if stype == curr_type:
            curr_group.append(s)
        else:
            bx = min(g[0] for g in curr_group)
            by = min(g[1] for g in curr_group)
            bw = max(g[0] + g[2] for g in curr_group) - bx
            bh = max(g[1] + g[3] for g in curr_group) - by
            regions.append({
                "type": curr_type,
                "bbox": (bx, by, bw, bh),
                "confidence": 0.92 if curr_type in ("text", "heading") else 0.89,
                "strip_count": len(curr_group)
            })
            curr_type = stype
            curr_group = [s]

    if curr_group:
        bx = min(g[0] for g in curr_group)
        by = min(g[1] for g in curr_group)
        bw = max(g[0] + g[2] for g in curr_group) - bx
        bh = max(g[1] + g[3] for g in curr_group) - by
        regions.append({
            "type": curr_type,
            "bbox": (bx, by, bw, bh),
            "confidence": 0.92 if curr_type in ("text", "heading") else 0.89,
            "strip_count": len(curr_group)
        })

    # Post-process: If a single isolated 1-strip 'diagram' is surrounded by text, merge into text unless tall
    filtered_regions = []
    for r in regions:
        if r["type"] == "diagram" and r["strip_count"] == 1 and r["bbox"][3] < median_h * 2.2:
            r["type"] = "text"
        filtered_regions.append(r)

    # Merge adjacent same-type regions if any
    final_regions = []
    for r in filtered_regions:
        if final_regions and final_regions[-1]["type"] == r["type"]:
            prev = final_regions[-1]
            nbx = min(prev["bbox"][0], r["bbox"][0])
            nby = min(prev["bbox"][1], r["bbox"][1])
            nbw = max(prev["bbox"][0] + prev["bbox"][2], r["bbox"][0] + r["bbox"][2]) - nbx
            nbh = max(prev["bbox"][1] + prev["bbox"][3], r["bbox"][1] + r["bbox"][3]) - nby
            prev["bbox"] = (nbx, nby, nbw, nbh)
            prev["strip_count"] += r["strip_count"]
        else:
            final_regions.append(r)

    print(f"\n=== {p.name} ({w}x{h}) | median line height: {median_h:.1f}px ===")
    for r in final_regions:
        bx, by, bw, bh = r["bbox"]
        print(f"  [{r['type'].upper()}] bbox=[x={bx}, y={by}, w={bw}, h={bh}] (strips: {r['strip_count']}, conf: {r['confidence']})")
    return final_regions

analyze_layout_multi_signal("backend/uploads/handwritten/13/processed/page_001.png")
analyze_layout_multi_signal("backend/uploads/handwritten/12/processed/page_001.png")
analyze_layout_multi_signal("backend/uploads/handwritten/10/processed/page_001.png")
analyze_layout_multi_signal("uploads/handwritten/1/processed/page_001.png")
analyze_layout_multi_signal("uploads/handwritten/4/processed/page_001.png")

