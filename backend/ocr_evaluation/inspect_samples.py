import os
import cv2
from PIL import Image

sample_paths = [
    ("Doc 10 (Poem/General)", "backend/uploads/handwritten/10/source/bf52e322cce0a39def5e858e7c70a25d.jpg"),
    ("Doc 12 (Networks Notes)", "backend/uploads/handwritten/12/source/text-to-handwriting.pdf"),
    ("Doc 13 (CSS/Web Notes)", "backend/uploads/handwritten/13/source/Complete-PYhton-Handwritten-Notes-28-11.webp"),
    ("Root Sample 1 (Physics)", "uploads/handwritten/1/source/physics_notes.png"),
    ("Root Sample 2 (Lecture)", "uploads/handwritten/2/source/multipage_lecture.pdf"),
    ("Root Sample 3 (Math)", "uploads/handwritten/3/source/faint_math.png"),
    ("Root Sample 4 (Blank)", "uploads/handwritten/4/source/blank_page.png"),
]

for label, p in sample_paths:
    exists = os.path.exists(p)
    print(f"[{label}] Path: {p} | Exists: {exists}")
    if exists:
        sz = os.path.getsize(p)
        print(f"  File size: {sz} bytes")
        if p.endswith(('.png', '.jpg', '.webp')):
            try:
                img = Image.open(p)
                print(f"  Dimensions: {img.size}, Mode: {img.mode}, Format: {img.format}")
            except Exception as e:
                print(f"  PIL error: {e}")

