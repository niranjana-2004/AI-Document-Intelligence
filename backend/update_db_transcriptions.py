import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.handwritten_page import HandwrittenPage
from app.services.handwriting.transcription_pipeline import transcribe_page_image
from app.api.routes.handwritten import _update_document_full_text
from pathlib import Path

def update_document(doc_id: int):
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            print(f"Document {doc_id} not found.")
            return

        print(f"\nProcessing Document {doc.id}: {doc.filename}")
        pages = db.query(HandwrittenPage).filter(HandwrittenPage.document_id == doc.id).order_by(HandwrittenPage.page_number.asc()).all()
        print(f"Total pages in DB: {len(pages)}")

        for page in pages:
            proc_p = Path(page.processed_image_path or page.original_image_path)
            orig_p = Path(page.original_image_path) if page.original_image_path else None
            
            if not proc_p.exists():
                print(f"Page {page.page_number} processed image not found at {proc_p}")
                continue

            print(f"Transcribing Page {page.page_number}...")
            res = transcribe_page_image(proc_p, original_image_path=orig_p)
            
            page.raw_transcription = res["full_text"]
            page.edited_transcription = res["full_text"]
            page.confidence_score = res["confidence_score"]
            page.ocr_metadata = {
                "lines": res["lines"],
                "is_empty": res["is_empty"],
                "execution_time_ms": res["execution_time_ms"]
            }
            page.status = "transcribed"
            page.error_message = None
            db.commit()
            print(f"Page {page.page_number} updated: {len(res['lines'])} lines, confidence: {res['confidence_score']}%")

        _update_document_full_text(doc, db)
        doc.processing_status = "transcribed"
        db.commit()
        print(f"Document {doc.id} successfully updated with complete transcriptions.")
    finally:
        db.close()

if __name__ == "__main__":
    # Update Document 12
    update_document(12)
    # Check Document 11 as well
    update_document(11)
