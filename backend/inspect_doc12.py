import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.handwritten_page import HandwrittenPage
from app.models.document import Document

db = SessionLocal()
try:
    doc = db.query(Document).filter(Document.id == 12).first()
    print(f"Document #12: {doc.filename}, is_handwritten={doc.is_handwritten}")
    pages = db.query(HandwrittenPage).filter(HandwrittenPage.document_id == 12).order_by(HandwrittenPage.page_number).all()
    print(f"Total pages in DB: {len(pages)}")
    for p in pages:
        text = p.edited_transcription or p.raw_transcription or ""
        print(f"--- PAGE {p.page_number} --- (confidence: {p.confidence_score}, status: {p.status})")
        print(f"Length: {len(text)} characters")
        print("Text preview:")
        print(text[:300] if text else "<EMPTY>")
        print("-" * 50)
finally:
    db.close()
