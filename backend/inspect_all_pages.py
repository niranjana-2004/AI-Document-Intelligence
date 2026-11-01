import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

from app.services.handwriting.image_preprocessor import read_image_safe
from app.services.handwriting.line_segmenter import segment_page_into_lines

def inspect_all_pages():
    orig_dir = Path("uploads/handwritten/12/original")
    proc_dir = Path("uploads/handwritten/12/processed")
    
    for page_num in range(1, 8):
        orig_path = orig_dir / f"page_{page_num:03d}.png"
        proc_path = proc_dir / f"page_{page_num:03d}.png"
        
        orig_img = read_image_safe(orig_path)
        proc_img = read_image_safe(proc_path)
        
        orig_lines, orig_empty = segment_page_into_lines(orig_img)
        proc_lines, proc_empty = segment_page_into_lines(proc_img)
        
        orig_heights = [l.bbox[3] for l in orig_lines]
        proc_heights = [l.bbox[3] for l in proc_lines]
        
        print(f"=== PAGE {page_num} ===")
        print(f"Orig lines: {len(orig_lines)} (empty={orig_empty}) | Heights: min={min(orig_heights) if orig_heights else 0}, max={max(orig_heights) if orig_heights else 0}, median={int(np.median(orig_heights)) if orig_heights else 0}")
        print(f"Proc lines: {len(proc_lines)} (empty={proc_empty}) | Heights: min={min(proc_heights) if proc_heights else 0}, max={max(proc_heights) if proc_heights else 0}, median={int(np.median(proc_heights)) if proc_heights else 0}")
        if len(orig_lines) < 20 and len(proc_lines) >= 20:
            print(f"--> Notice: Orig merged lines ({len(orig_lines)} vs {len(proc_lines)})!")

if __name__ == "__main__":
    inspect_all_pages()

