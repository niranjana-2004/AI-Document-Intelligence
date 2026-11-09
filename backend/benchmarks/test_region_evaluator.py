import cv2
import numpy as np
from pathlib import Path
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

def detect_regions(img_path):
    p = Path(img_path)
    if not p.exists():
        p = Path("D:/AI-Document-Intelligence") / img_path
    img = cv2.imread(str(p))
    if img is None:
        raise ValueError(f"Cannot read {img_path}")
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    std_val = float(np.std(gray))
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ink_ratio = np.sum(thresh > 0) / (h * w)

    if std_val < 3.0 or ink_ratio < 0.0005:
        return [{"type": "background", "bbox": (0, 0, w, h), "confidence": 1.0, "strips": 0}]

    # Border clear (scanner artifacts)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(thresh)
    border_mask = np.zeros_like(thresh)
    for i in range(1, num_labels):
        bx = stats[i, cv2.CC_STAT_LEFT]
        by = stats[i, cv2.CC_STAT_TOP]
        bw = stats[i, cv2.CC_STAT_WIDTH]
        bh = stats[i, cv2.CC_STAT_HEIGHT]
        if (bx <= 4 or by <= 4 or (bx + bw) >= w - 4 or (by + bh) >= h - 4) and (bw > w * 0.50 or bh > h * 0.30):
            border_mask[labels == i] = 255
    clean = cv2.subtract(thresh, border_mask)

    # Suppress ruling lines
    line_len = max(30, int(w * 0.15))
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (line_len, 1))
    ruling_lines = cv2.morphologyEx(clean, cv2.MORPH_OPEN, kernel_h)
    text_thresh = cv2.subtract(clean, ruling_lines)

    # Horizontal projection profile
    row_ink = np.sum(text_thresh > 0, axis=1).astype(np.float32)
    sigma = max(4.0, min(8.0, h / 240.0))
    smoothed = gaussian_filter1d(row_ink, sigma=sigma)

    min_dist = max(18, int(h * 0.014))
    active_ink = smoothed[smoothed > 0]
    prominence = max(15.0, float(np.percentile(active_ink, 20)) * 0.35) if len(active_ink) > 0 else 18.0
    peaks, _ = find_peaks(smoothed, distance=min_dist, prominence=prominence)
    min_peak_ink = max(20.0, 0.012 * w)
    valid_peaks = [pk for pk in peaks if smoothed[pk] >= min_peak_ink]

    if not valid_peaks:
        return [{"type": "text", "bbox": (0, 0, w, h), "confidence": 0.85, "strips": 1}]

    search_top = max(0, int(valid_peaks[0] - (min_dist * 1.5)))
    first_ink = np.where(row_ink[search_top:valid_peaks[0]] > max(8, 0.004 * w))[0]
    top_y = max(0, search_top + first_ink[0] - 6) if len(first_ink) > 0 else max(0, int(valid_peaks[0] - (min_dist * 0.8)))

    valleys = [top_y]
    for i in range(len(valid_peaks) - 1):
        p1, p2 = valid_peaks[i], valid_peaks[i + 1]
        valleys.append(p1 + int(np.argmin(smoothed[p1:p2])))

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
        strip_thresh = clean[y1:y2, :]
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

    k_v = cv2.getStructuringElement(cv2.MORPH_RECT, (2, int(median_h * 0.55)))
    v_lines = cv2.morphologyEx(clean, cv2.MORPH_OPEN, k_v)

    strip_types = []
    for (sx, sy, sw, sh) in strips:
        sub_v = v_lines[sy:sy+sh, sx:sx+sw]
        v_pix = np.sum(sub_v > 0)
        is_tall = sh > median_h * 1.8
        has_v = v_pix > max(50, int(sh * 1.2))

        if (is_tall and has_v) or (sh > median_h * 2.2):
            strip_types.append("diagram")
        elif (sy / float(h)) < 0.12 and sh <= median_h * 1.5:
            strip_types.append("heading")
        else:
            strip_types.append("text")

    # Bridge small gaps between diagram strips within diagram zone
    for i in range(1, len(strip_types) - 1):
        if strip_types[i] == "text" and strip_types[i-1] == "diagram" and strip_types[i+1] == "diagram":
            strip_types[i] = "diagram"
    for i in range(1, len(strip_types) - 2):
        if strip_types[i] == "text" and strip_types[i+1] == "text":
            if strip_types[i-1] == "diagram" and strip_types[i+2] == "diagram":
                strip_types[i] = "diagram"
                strip_types[i+1] = "diagram"

    # Group consecutive strips
    groups = []
    curr_type = strip_types[0]
    curr_strips = [strips[0]]
    for s, stype in zip(strips[1:], strip_types[1:]):
        if stype == curr_type:
            curr_strips.append(s)
        else:
            bx = min(g[0] for g in curr_strips)
            by = min(g[1] for g in curr_strips)
            bw = max(g[0] + g[2] for g in curr_strips) - bx
            bh = max(g[1] + g[3] for g in curr_strips) - by
            groups.append({
                "type": curr_type,
                "bbox": (int(bx), int(by), int(bw), int(bh)),
                "strips": len(curr_strips),
                "confidence": 0.92 if curr_type in ("text", "heading") else 0.89
            })
            curr_type = stype
            curr_strips = [s]
    if curr_strips:
        bx = min(g[0] for g in curr_strips)
        by = min(g[1] for g in curr_strips)
        bw = max(g[0] + g[2] for g in curr_strips) - bx
        bh = max(g[1] + g[3] for g in curr_strips) - by
        groups.append({
            "type": curr_type,
            "bbox": (int(bx), int(by), int(bw), int(bh)),
            "strips": len(curr_strips),
            "confidence": 0.92 if curr_type in ("text", "heading") else 0.89
        })

    # Filter isolated 1-strip diagram if small
    filtered = []
    for g in groups:
        if g["type"] == "diagram" and g["strips"] == 1 and g["bbox"][3] < median_h * 2.2:
            g["type"] = "text"
        if filtered and filtered[-1]["type"] == g["type"]:
            prev = filtered[-1]
            nbx = min(prev["bbox"][0], g["bbox"][0])
            nby = min(prev["bbox"][1], g["bbox"][1])
            nbw = max(prev["bbox"][0] + prev["bbox"][2], g["bbox"][0] + g["bbox"][2]) - nbx
            nbh = max(prev["bbox"][1] + prev["bbox"][3], g["bbox"][1] + g["bbox"][3]) - nby
            prev["bbox"] = (int(nbx), int(nby), int(nbw), int(nbh))
            prev["strips"] += g["strips"]
        else:
            filtered.append(g)

    return filtered

if __name__ == "__main__":
    samples = [
        ("Doc 13 (CSS Diagram)", "backend/uploads/handwritten/13/processed/page_001.png"),
        ("Doc 12 P1 (Networks)", "backend/uploads/handwritten/12/processed/page_001.png"),
        ("Doc 12 P4 (Networks)", "backend/uploads/handwritten/12/processed/page_004.png"),
        ("Doc 10 P1 (Poetry)", "backend/uploads/handwritten/10/processed/page_001.png"),
        ("Root 1 (Physics)", "uploads/handwritten/1/processed/page_001.png"),
        ("Root 2 P1 (Physics)", "uploads/handwritten/2/processed/page_001.png"),
        ("Root 2 P2 (Thermodynamics)", "uploads/handwritten/2/processed/page_002.png"),
        ("Root 3 (Math)", "uploads/handwritten/3/processed/page_001.png"),
        ("Root 4 (Blank Negative)", "uploads/handwritten/4/processed/page_001.png")
    ]
    for name, path in samples:
        res = detect_regions(path)
        print(f"\n=== {name} ===")
        for r in res:
            t = r["type"].upper()
            bb = r["bbox"]
            st = r.get("strips", 1)
            cf = r["confidence"]
            print(f"  [{t}] bbox={bb}, strips={st}, conf={cf}")
