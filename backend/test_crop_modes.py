import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
from PIL import Image, ImageEnhance
from app.services.handwriting.ocr_service import get_ocr_engine

model, processor = get_ocr_engine()

base_dir = os.path.dirname(os.path.abspath(__file__))
orig_img = cv2.imread(os.path.join(base_dir, "uploads/handwritten/12/original/page_002.png"))
proc_img = cv2.imread(os.path.join(base_dir, "uploads/handwritten/12/processed/page_002.png"))

# Crop 5: y=575 to 659
crop_orig = Image.fromarray(cv2.cvtColor(orig_img[575:659, :], cv2.COLOR_BGR2RGB))
crop_proc = Image.fromarray(cv2.cvtColor(proc_img[575:659, :], cv2.COLOR_BGR2RGB))

def infer(img, name):
    pv = processor(img.convert("RGB"), return_tensors="pt").pixel_values
    out = model.generate(pv, max_new_tokens=96, num_beams=4)
    txt = processor.batch_decode(out, skip_special_tokens=True)[0]
    print(f"{name}: '{txt}'")

print("GT: '- Service unavailability: Web servers and APIs stop accepting new'")
infer(crop_orig, "1. ORIGINAL crop")
infer(crop_proc, "2. PROCESSED crop")
infer(ImageEnhance.Sharpness(crop_orig).enhance(2.0), "3. ORIGINAL sharpened")
infer(ImageEnhance.Contrast(crop_orig).enhance(1.5), "4. ORIGINAL contrast")
