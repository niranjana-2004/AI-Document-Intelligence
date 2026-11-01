import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from pathlib import Path
from app.services.handwriting.transcription_pipeline import transcribe_page_image
from benchmark_ocr import run_benchmark

def main():
    proc_dir = Path("backend/uploads/handwritten/12/processed")
    transcriptions = {}
    
    for page_num in range(1, 8):
        proc_path = proc_dir / f"page_{page_num:03d}.png"
        orig_path = Path(f"backend/uploads/handwritten/12/pages/page_{page_num:03d}.png")
        res = transcribe_page_image(proc_path, original_image_path=orig_path)
        transcriptions[page_num] = res["full_text"]
        print(f"Page {page_num}: {res['total_lines']} lines, confidence: {res['confidence_score']}%, chars: {len(res['full_text'])}")
        
    print("\nRunning Benchmark against Ground Truth...")
    run_benchmark(transcriptions, label="PRODUCTION PIPELINE (transcribe_page_image)")

if __name__ == "__main__":
    main()
