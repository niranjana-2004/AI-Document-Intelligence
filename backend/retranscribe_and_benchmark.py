import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.handwritten_page import HandwrittenPage
from app.api.routes.handwritten import _run_ocr_for_document
from benchmark_ocr import run_benchmark

def main():
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == 12).first()
        if not doc:
            print("Document 12 not found!")
            return

        print(f"Starting re-transcription of Document #{doc.id} ({doc.filename}) with 3.0 pipeline...")
        t0 = time.time()
        _run_ocr_for_document(doc, db)
        elapsed = time.time() - t0
        print(f"Re-transcription complete in {elapsed:.2f}s!")

        # Refresh pages
        pages = db.query(HandwrittenPage).filter(HandwrittenPage.document_id == 12).order_by(HandwrittenPage.page_number).all()
        transcriptions_raw = {}
        transcriptions_edited = {}

        for p in pages:
            transcriptions_raw[p.page_number] = p.raw_transcription or ""
            transcriptions_edited[p.page_number] = p.edited_transcription or ""
            print(f"Page {p.page_number}: conf={p.confidence_score}%, lines={len(p.ocr_metadata.get('lines', []))}, blocks={len(p.ocr_metadata.get('structured_layout', {}).get('blocks', []))}")

        print("\n--- BENCHMARK 1: RAW OCR LINES (NO FORMATTING) ---")
        run_benchmark(transcriptions_raw, label="NEW 3.0 OVERHAULED PIPELINE (RAW LINES)")

        print("\n--- BENCHMARK 2: STRUCTURED / EDITED TRANSCRIPTION ---")
        run_benchmark(transcriptions_edited, label="NEW 3.0 OVERHAULED PIPELINE (STRUCTURED MARKDOWN)")

    finally:
        db.close()

if __name__ == "__main__":
    main()
