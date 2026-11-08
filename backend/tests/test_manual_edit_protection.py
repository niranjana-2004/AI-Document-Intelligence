import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.handwritten_page import HandwrittenPage
from app.api.routes.handwritten import _run_ocr_for_document

def test_manual_edit_protection_flow():
    db = SessionLocal()
    try:
        # Pick Document #12 Page 1
        page = db.query(HandwrittenPage).filter(
            HandwrittenPage.document_id == 12,
            HandwrittenPage.page_number == 1
        ).first()
        assert page is not None, "Document #12 Page 1 not found"

        original_raw = page.raw_transcription
        original_edited = page.edited_transcription
        original_meta = dict(page.ocr_metadata or {})

        print(f"[STEP 1] Initial state: has_raw={bool(original_raw)}, has_edited={bool(original_edited)}")

        # User simulates manual edit
        custom_manual_text = "MANUAL EDIT BY STUDENT: Niranjana A S 21BIT042 Verified Notes"
        meta = dict(page.ocr_metadata or {})
        meta["is_manually_edited"] = True
        meta["user_manual_transcription"] = custom_manual_text
        meta["manual_edit_timestamp"] = 123456789.0
        page.ocr_metadata = meta
        page.edited_transcription = custom_manual_text
        db.commit()

        print("[STEP 2] Applied user manual edit and flagged is_manually_edited=True")

        # Now re-run document OCR pipeline
        doc = db.query(Document).filter(Document.id == 12).first()
        print("[STEP 3] Re-running document OCR and recovery pipeline...")
        _run_ocr_for_document(doc, db)

        # Refresh page from DB
        db.expire_all()
        page_reloaded = db.query(HandwrittenPage).filter(
            HandwrittenPage.document_id == 12,
            HandwrittenPage.page_number == 1
        ).first()

        print(f"[STEP 4] Checking re-transcribed page:")
        print(f"  edited_transcription: '{page_reloaded.edited_transcription[:60]}...'")
        print(f"  is_manually_edited flag: {page_reloaded.ocr_metadata.get('is_manually_edited')}")
        print(f"  user_manual_transcription: '{page_reloaded.ocr_metadata.get('user_manual_transcription')[:60]}...'")

        assert page_reloaded.edited_transcription == custom_manual_text, "Manual edit was OVERWRITTEN by automated pipeline!"
        assert page_reloaded.ocr_metadata.get("is_manually_edited") is True, "is_manually_edited flag was cleared!"
        assert page_reloaded.ocr_metadata.get("user_manual_transcription") == custom_manual_text

        print("\n[VERIFICATION PASSED] User manual edit successfully preserved across automated re-OCR!")

        # Restore original state
        page_reloaded.edited_transcription = original_edited
        page_reloaded.ocr_metadata = original_meta
        db.commit()
        print("[CLEANUP] Page 1 restored to original benchmark state.")

    finally:
        db.close()

if __name__ == "__main__":
    test_manual_edit_protection_flow()

