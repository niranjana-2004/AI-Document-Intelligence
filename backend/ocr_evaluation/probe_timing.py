import os
import sys
import time
from PIL import Image

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.core.database import SessionLocal
from app.models.handwritten_page import HandwrittenPage
from ocr_evaluation.models import load_trocr_small, load_trocr_base, run_single_inference, unload_model

def probe():
    db = SessionLocal()
    page1 = db.query(HandwrittenPage).filter(HandwrittenPage.document_id == 12, HandwrittenPage.page_number == 1).first()
    lines = page1.ocr_metadata.get("lines", [])[:5]
    img_path = os.path.join(backend_dir, page1.processed_image_path)
    page_img = Image.open(img_path).convert("RGB")
    crops = []
    for l in lines:
        bx, by, bw, bh = l["bbox"]
        crops.append(page_img.crop((bx, by, bx + bw, by + bh)))
    db.close()

    print("--- Probing TrOCR Small on 5 lines ---")
    s_model, s_proc, s_load = load_trocr_small()
    s_times = []
    for i, c in enumerate(crops):
        res = run_single_inference(s_model, s_proc, c)
        s_times.append(res["inference_time_ms"])
        print(f"Small Line {i+1}: '{res['text']}' in {res['inference_time_ms']:.1f}ms (conf: {res['confidence']}%)")
    unload_model(s_model, s_proc)

    print(f"Small avg inference time: {sum(s_times)/len(s_times):.1f}ms")

    print("\n--- Probing TrOCR Base on 5 lines ---")
    b_model, b_proc, b_load = load_trocr_base()
    b_times = []
    for i, c in enumerate(crops):
        res = run_single_inference(b_model, b_proc, c)
        b_times.append(res["inference_time_ms"])
        print(f"Base Line {i+1}: '{res['text']}' in {res['inference_time_ms']:.1f}ms (conf: {res['confidence']}%)")
    unload_model(b_model, b_proc)

    print(f"Base avg inference time: {sum(b_times)/len(b_times):.1f}ms")
    print(f"Relative slowdown factor: {(sum(b_times)/len(b_times)) / (sum(s_times)/len(s_times)):.2f}x")

if __name__ == "__main__":
    probe()

