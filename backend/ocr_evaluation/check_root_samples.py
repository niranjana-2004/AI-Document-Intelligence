import os
import pypdfium2 as pdfium
from PIL import Image

def inspect_img(path):
    if not os.path.exists(path):
        return "MISSING"
    if path.endswith('.pdf'):
        pdf = pdfium.PdfDocument(path)
        return f"PDF with {len(pdf)} pages"
    img = Image.open(path)
    return f"Image {img.size}, mode={img.mode}"

for root_id in [1, 2, 3, 4]:
    src_dir = f"uploads/handwritten/{root_id}/source"
    if os.path.exists(src_dir):
        files = os.listdir(src_dir)
        for f in files:
            full_p = os.path.join(src_dir, f)
            print(f"Sample {root_id}: {f} -> {inspect_img(full_p)}")

