import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.sql import func

from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.user import User
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.handwritten_page import HandwrittenPage
from app.models.activity import ActivityLog
from app.services.handwriting.pdf_rasterizer import rasterize_document_to_images
from app.services.handwriting.image_preprocessor import (
    preprocess_handwritten_image,
    generate_page_stages
)
from app.services.handwriting.transcription_pipeline import transcribe_page_image
from app.services.handwriting.subject_service import (
    ACADEMIC_SUBJECTS,
    auto_detect_and_set_subject,
    set_document_subject
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/handwritten",
    tags=["Handwritten Notes"]
)

HANDWRITTEN_BASE_DIR = Path("uploads") / "handwritten"
HANDWRITTEN_BASE_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"
}


class TranscriptionUpdateRequest(BaseModel):
    transcription: str


class SubjectUpdateRequest(BaseModel):
    subject: str


def _update_document_full_text(document: Document, db: Session) -> str:
    """
    Reassemble consolidated document text across all pages in reading order,
    and synchronize semantic DocumentChunk embeddings.
    """
    pages = (
        db.query(HandwrittenPage)
        .filter(HandwrittenPage.document_id == document.id)
        .order_by(HandwrittenPage.page_number.asc())
        .all()
    )
    text_sections = []
    for p in pages:
        content = (p.edited_transcription or p.raw_transcription or "").strip()
        if content:
            text_sections.append(f"--- Page {p.page_number} ---\n{content}")

    full_text = "\n\n".join(text_sections)
    document.extracted_text = full_text
    document.text_length = len(full_text)
    db.commit()

    # Synchronize chunks and embeddings in background or inline
    try:
        from app.services.handwriting.handwritten_source_service import sync_handwritten_chunks_and_embeddings
        sync_handwritten_chunks_and_embeddings(document.id, db)
    except Exception as e:
        logger.warning(f"Could not synchronize chunks for doc #{document.id}: {e}")

    return full_text


@router.post("/upload")
async def upload_handwritten_document(
    file: UploadFile = File(...),
    auto_ocr: bool = Query(False, description="Whether to automatically run OCR after preprocessing"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload and preprocess a multi-page handwritten PDF or image.
    1. Validates file format.
    2. Rasterizes PDF or loads image into individual high-res original pages.
    3. Runs automated computer vision preprocessing (deskew, CLAHE contrast, shadow removal, denoising).
    4. Persists document and page tracking records with user tenant isolation.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is missing."
        )

    raw_filename = Path(file.filename).name
    file_extension = Path(raw_filename).suffix.lower()

    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{file_extension}'. Allowed formats: PDF, PNG, JPG, WEBP, TIFF."
        )

    file_content = await file.read()
    if len(file_content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty."
        )

    # 1. Create initial Document record in SQLite
    document = Document(
        filename=raw_filename,
        document_type="HANDWRITTEN",
        file_path="",  # will be updated with permanent path
        extracted_text="",
        text_length=0,
        summary=None,
        is_handwritten=True,
        processing_status="processing",
        processing_progress=0,
        user_id=current_user.id
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # 2. Setup document folder hierarchy
    doc_dir = HANDWRITTEN_BASE_DIR / str(document.id)
    source_dir = doc_dir / "source"
    original_dir = doc_dir / "original"
    processed_dir = doc_dir / "processed"

    source_dir.mkdir(parents=True, exist_ok=True)
    original_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    source_path = source_dir / raw_filename
    with open(source_path, "wb") as buffer:
        buffer.write(file_content)

    document.file_path = str(source_path)
    db.commit()

    # 3. Rasterize document to high-resolution page images
    try:
        page_items = rasterize_document_to_images(
            file_path=source_path,
            output_dir=original_dir,
            dpi=200
        )
    except Exception as error:
        document.processing_status = "failed"
        db.commit()
        logger.error(f"Failed to rasterize document {document.id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to extract document pages: {str(error)}"
        )

    total_pages = len(page_items)
    page_records = []

    # 4. Preprocess each page image
    for idx, page_info in enumerate(page_items):
        page_num = page_info["page_number"]
        orig_img_path = Path(page_info["image_path"])
        proc_img_path = processed_dir / f"page_{page_num:03d}.png"

        try:
            preprocess_meta = preprocess_handwritten_image(
                input_path=orig_img_path,
                output_path=proc_img_path
            )
            page_status = "completed"
            err_msg = None
        except Exception as proc_err:
            logger.warning(f"Preprocessing error on page {page_num} of doc {document.id}: {proc_err}")
            proc_img_path = orig_img_path  # fallback to original
            page_status = "completed"
            err_msg = str(proc_err)

        handwritten_page = HandwrittenPage(
            document_id=document.id,
            page_number=page_num,
            original_image_path=str(orig_img_path),
            processed_image_path=str(proc_img_path),
            raw_transcription=None,
            edited_transcription=None,
            confidence_score=None,
            has_math=False,
            has_diagrams=False,
            status=page_status,
            error_message=err_msg
        )
        db.add(handwritten_page)

        # Update document progress
        progress_pct = int(((idx + 1) / total_pages) * 100)
        document.processing_progress = progress_pct
        db.commit()
        db.refresh(handwritten_page)

        page_records.append({
            "page_number": page_num,
            "width": page_info["width"],
            "height": page_info["height"],
            "status": page_status,
            "original_image_url": f"/handwritten/{document.id}/pages/{page_num}/image?version=original",
            "processed_image_url": f"/handwritten/{document.id}/pages/{page_num}/image?version=processed"
        })

    # Mark document ready for OCR & transcription studio
    document.processing_status = "ready"
    document.processing_progress = 100
    db.commit()

    # Record user activity
    activity = ActivityLog(
        user_id=current_user.id,
        activity_type="handwritten_upload"
    )
    db.add(activity)
    db.commit()

    # If auto_ocr is requested, trigger OCR immediately
    if auto_ocr:
        _run_ocr_for_document(document, db)

    return {
        "message": f"Successfully preprocessed {total_pages} page(s).",
        "document_id": document.id,
        "filename": document.filename,
        "total_pages": total_pages,
        "processing_status": document.processing_status,
        "processing_progress": document.processing_progress,
        "created_at": document.created_at,
        "pages": page_records
    }


def _run_ocr_for_document(document: Document, db: Session) -> Dict[str, Any]:
    """Internal helper to execute OCR across all pages of a document."""
    pages = (
        db.query(HandwrittenPage)
        .filter(HandwrittenPage.document_id == document.id)
        .order_by(HandwrittenPage.page_number.asc())
        .all()
    )

    document.processing_status = "transcribing"
    db.commit()

    total_pages = len(pages)
    for idx, page in enumerate(pages):
        img_to_ocr = Path(page.processed_image_path or page.original_image_path)
        orig_img = Path(page.original_image_path) if page.original_image_path else None
        try:
            ocr_res = transcribe_page_image(
                img_to_ocr,
                original_image_path=orig_img,
                subject=document.subject,
                page_num=page.page_number
            )
            existing_meta = page.ocr_metadata or {}
            is_manual = existing_meta.get("is_manually_edited", False)
            user_manual_text = existing_meta.get("user_manual_transcription")

            page.raw_transcription = ocr_res.get("raw_text") or ocr_res["full_text"]
            if is_manual and user_manual_text:
                page.edited_transcription = user_manual_text
            else:
                page.edited_transcription = ocr_res["full_text"]

            page.confidence_score = ocr_res["confidence_score"]
            page.ocr_metadata = {
                "lines": ocr_res["lines"],
                "is_empty": ocr_res["is_empty"],
                "execution_time_ms": ocr_res["execution_time_ms"],
                "structured_layout": ocr_res.get("structured_layout", {}),
                "technical_corrections": ocr_res.get("technical_corrections", []),
                "tokens": ocr_res.get("tokens", []),
                "is_manually_edited": is_manual,
                "user_manual_transcription": user_manual_text,
                "ai_recovered_transcription": ocr_res["full_text"]
            }
            page.status = "transcribed"
            page.error_message = None
            print(f" Transcribed Page {page.page_number}/{total_pages} ({len(ocr_res.get('lines', []))} lines, {len(ocr_res.get('technical_corrections', []))} corrs)...", flush=True)
        except Exception as ocr_err:
            logger.error(f"OCR failed on doc {document.id} page {page.page_number}: {ocr_err}")
            page.status = "failed"
            page.error_message = str(ocr_err)

        db.commit()

    _update_document_full_text(document, db)
    document.processing_status = "transcribed"
    db.commit()


@router.post("/{document_id}/ocr")
def process_document_ocr(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Trigger or re-run handwriting OCR recognition for all pages of a document.
    """
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == current_user.id,
            Document.is_handwritten == True
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Handwritten document not found."
        )

    _run_ocr_for_document(document, db)

    pages = (
        db.query(HandwrittenPage)
        .filter(HandwrittenPage.document_id == document.id)
        .order_by(HandwrittenPage.page_number.asc())
        .all()
    )

    return {
        "message": "Handwriting OCR completed successfully.",
        "document_id": document.id,
        "processing_status": document.processing_status,
        "total_pages": len(pages),
        "extracted_text": document.extracted_text,
        "pages": [
            {
                "page_number": p.page_number,
                "status": p.status,
                "confidence_score": p.confidence_score,
                "transcription": p.edited_transcription or p.raw_transcription,
                "line_count": len((p.ocr_metadata or {}).get("lines", [])) if p.ocr_metadata else 0,
                "error": p.error_message
            }
            for p in pages
        ]
    }


@router.post("/{document_id}/pages/{page_number}/ocr")
def process_single_page_ocr(
    document_id: int,
    page_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Trigger or retry handwriting OCR recognition for a specific page.
    """
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == current_user.id,
            Document.is_handwritten == True
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Handwritten document not found."
        )

    page = (
        db.query(HandwrittenPage)
        .filter(
            HandwrittenPage.document_id == document_id,
            HandwrittenPage.page_number == page_number
        )
        .first()
    )

    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_number} not found."
        )

    img_to_ocr = Path(page.processed_image_path or page.original_image_path)
    orig_img = Path(page.original_image_path) if page.original_image_path else None
    try:
        ocr_res = transcribe_page_image(
            img_to_ocr,
            original_image_path=orig_img,
            subject=document.subject,
            page_num=page_number
        )
        existing_meta = page.ocr_metadata or {}
        is_manual = existing_meta.get("is_manually_edited", False)
        user_manual_text = existing_meta.get("user_manual_transcription")

        page.raw_transcription = ocr_res.get("raw_text") or ocr_res["full_text"]
        if is_manual and user_manual_text:
            page.edited_transcription = user_manual_text
        else:
            page.edited_transcription = ocr_res["full_text"]

        page.confidence_score = ocr_res["confidence_score"]
        page.ocr_metadata = {
            "lines": ocr_res["lines"],
            "is_empty": ocr_res["is_empty"],
            "execution_time_ms": ocr_res["execution_time_ms"],
            "structured_layout": ocr_res.get("structured_layout", {}),
            "technical_corrections": ocr_res.get("technical_corrections", []),
            "tokens": ocr_res.get("tokens", []),
            "is_manually_edited": is_manual,
            "user_manual_transcription": user_manual_text,
            "ai_recovered_transcription": ocr_res["full_text"]
        }
        page.status = "transcribed"
        page.error_message = None
    except Exception as ocr_err:
        logger.error(f"OCR failed on doc {document.id} page {page_number}: {ocr_err}")
        page.status = "failed"
        page.error_message = str(ocr_err)

    db.commit()
    _update_document_full_text(document, db)

    return {
        "message": f"Page {page_number} OCR completed.",
        "page_number": page.page_number,
        "status": page.status,
        "confidence_score": page.confidence_score,
        "transcription": page.edited_transcription,
        "lines": (page.ocr_metadata or {}).get("lines", []),
        "error": page.error_message
    }


@router.post("/{document_id}/pages/{page_number}/lines/{line_index}/ocr")
def process_single_line_ocr(
    document_id: int,
    page_number: int,
    line_index: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Trigger re-recognition of an individual line on demand.
    """
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == current_user.id,
            Document.is_handwritten == True
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Handwritten document not found."
        )

    page = (
        db.query(HandwrittenPage)
        .filter(
            HandwrittenPage.document_id == document_id,
            HandwrittenPage.page_number == page_number
        )
        .first()
    )

    if not page or not page.ocr_metadata or "lines" not in page.ocr_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Line data for page {page_number} not found."
        )

    lines = list(page.ocr_metadata.get("lines", []))
    target_line = None
    for l in lines:
        if l.get("line_index") == line_index:
            target_line = l
            break

    if not target_line:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Line {line_index} not found on page {page_number}."
        )

    bbox = target_line.get("bbox")
    if not bbox or len(bbox) != 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Line does not have valid bounding box coordinates."
        )

    img_path = Path(page.processed_image_path or page.original_image_path)
    from app.services.handwriting.image_preprocessor import read_image_safe
    from app.services.handwriting.ocr_service import recognize_line_image
    from PIL import Image
    import cv2

    proc_img = read_image_safe(img_path)
    bx, by, bw, bh = bbox
    crop = proc_img[by:by+bh, bx:bx+bw]
    pil_crop = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))

    res = recognize_line_image(pil_crop)
    new_text = res.get("text", "").strip()
    new_conf = res.get("confidence", 0.0)

    # Update line in metadata
    target_line["text"] = new_text
    target_line["confidence"] = new_conf
    target_line["is_uncertain"] = new_conf < 60.0

    # Reassemble page raw transcription
    page.raw_transcription = "\n".join([l.get("text", "") for l in lines if l.get("text")])
    if not page.edited_transcription or page.edited_transcription == page.raw_transcription:
        page.edited_transcription = page.raw_transcription

    confs = [l.get("confidence", 0.0) for l in lines if l.get("text")]
    if confs:
        page.confidence_score = round(sum(confs) / len(confs), 1)

    page.ocr_metadata["lines"] = lines
    flag_modified(page, "ocr_metadata")
    db.commit()
    _update_document_full_text(document, db)

    return {
        "message": f"Line {line_index} reprocessed successfully.",
        "line_index": line_index,
        "text": new_text,
        "confidence": new_conf,
        "page_confidence": page.confidence_score,
        "full_transcription": page.edited_transcription
    }


@router.put("/{document_id}/pages/{page_number}/transcription")
def update_page_transcription(
    document_id: int,
    page_number: int,
    body: TranscriptionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Save user corrections for a page transcription and update consolidated document text.
    """
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == current_user.id,
            Document.is_handwritten == True
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Handwritten document not found."
        )

    page = (
        db.query(HandwrittenPage)
        .filter(
            HandwrittenPage.document_id == document_id,
            HandwrittenPage.page_number == page_number
        )
        .first()
    )

    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_number} not found."
        )

    meta = page.ocr_metadata or {}
    meta["is_manually_edited"] = True
    meta["user_manual_transcription"] = body.transcription
    meta["manual_edit_timestamp"] = time.time()
    page.ocr_metadata = meta
    page.edited_transcription = body.transcription
    db.commit()

    # Reassemble consolidated document text
    full_text = _update_document_full_text(document, db)

    return {
        "message": f"Page {page_number} transcription updated successfully.",
        "document_id": document.id,
        "page_number": page.page_number,
        "transcription": page.edited_transcription,
        "full_text_length": len(full_text)
    }


@router.get("/")
def get_handwritten_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all handwritten documents uploaded by the current authenticated user.
    """
    documents = (
        db.query(Document)
        .filter(
            Document.user_id == current_user.id,
            Document.is_handwritten == True
        )
        .order_by(Document.created_at.desc())
        .all()
    )

    doc_list = []
    for doc in documents:
        page_count = (
            db.query(HandwrittenPage)
            .filter(HandwrittenPage.document_id == doc.id)
            .count()
        )
        doc_list.append({
            "id": doc.id,
            "filename": doc.filename,
            "document_type": doc.document_type,
            "subject": doc.subject or "Humanities & General",
            "processing_status": doc.processing_status,
            "processing_progress": doc.processing_progress,
            "page_count": page_count,
            "has_transcription": bool(doc.extracted_text and doc.extracted_text.strip()),
            "created_at": doc.created_at,
            "preview_url": f"/handwritten/{doc.id}/pages/1/image?version=processed" if page_count > 0 else None
        })

    return {
        "count": len(doc_list),
        "documents": doc_list
    }


@router.get("/{document_id}")
def get_handwritten_document_details(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed metadata for a single handwritten document.
    """
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == current_user.id,
            Document.is_handwritten == True
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Handwritten document not found."
        )

    pages = (
        db.query(HandwrittenPage)
        .filter(HandwrittenPage.document_id == document.id)
        .order_by(HandwrittenPage.page_number.asc())
        .all()
    )

    return {
        "id": document.id,
        "filename": document.filename,
        "document_type": document.document_type,
        "subject": document.subject or "Humanities & General",
        "available_subjects": ACADEMIC_SUBJECTS,
        "processing_status": document.processing_status,
        "processing_progress": document.processing_progress,
        "total_pages": len(pages),
        "summary": document.summary,
        "extracted_text": document.extracted_text,
        "created_at": document.created_at,
        "pages": [
            {
                "page_number": p.page_number,
                "status": p.status,
                "confidence_score": p.confidence_score,
                "has_math": p.has_math,
                "has_diagrams": p.has_diagrams,
                "raw_transcription": p.raw_transcription,
                "edited_transcription": p.edited_transcription,
                "ocr_metadata": p.ocr_metadata,
                "error": p.error_message,
                "original_image_url": f"/handwritten/{document.id}/pages/{p.page_number}/image?version=original",
                "processed_image_url": f"/handwritten/{document.id}/pages/{p.page_number}/image?version=processed"
            }
            for p in pages
        ]
    }


@router.get("/{document_id}/pages")
def get_handwritten_document_pages(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve all page items and status for a handwritten document.
    """
    document = (
        db.query(Document.id)
        .filter(
            Document.id == document_id,
            Document.user_id == current_user.id,
            Document.is_handwritten == True
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Handwritten document not found."
        )

    pages = (
        db.query(HandwrittenPage)
        .filter(HandwrittenPage.document_id == document_id)
        .order_by(HandwrittenPage.page_number.asc())
        .all()
    )

    return {
        "document_id": document_id,
        "total_pages": len(pages),
        "pages": [
            {
                "page_number": p.page_number,
                "status": p.status,
                "confidence_score": p.confidence_score,
                "has_math": p.has_math,
                "has_diagrams": p.has_diagrams,
                "raw_transcription": p.raw_transcription,
                "edited_transcription": p.edited_transcription,
                "ocr_metadata": p.ocr_metadata,
                "original_image_url": f"/handwritten/{document_id}/pages/{p.page_number}/image?version=original",
                "processed_image_url": f"/handwritten/{document_id}/pages/{p.page_number}/image?version=processed"
            }
            for p in pages
        ]
    }


@router.get("/{document_id}/pages/{page_number}/image")
def get_handwritten_page_image(
    document_id: int,
    page_number: int,
    version: str = Query("processed", pattern="^(processed|original)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Serve a preprocessed or original high-resolution page image.
    Enforces tenant access control and sets caching headers.
    """
    document = (
        db.query(Document.id)
        .filter(
            Document.id == document_id,
            Document.user_id == current_user.id
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )

    page = (
        db.query(HandwrittenPage)
        .filter(
            HandwrittenPage.document_id == document_id,
            HandwrittenPage.page_number == page_number
        )
        .first()
    )

    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_number} not found."
        )

    image_path_str = (
        page.processed_image_path if version == "processed" and page.processed_image_path
        else page.original_image_path
    )
    image_path = Path(image_path_str)

    if not image_path.exists():
        # Fallback to original if processed not yet created
        image_path = Path(page.original_image_path)
        if not image_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image file not found on disk."
            )

    return FileResponse(
        path=str(image_path),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"}
    )


STAGE_FILE_MAP = {
    "original": "stage_1_original",
    "deskewed": "stage_2_deskewed",
    "normalized": "stage_3_normalized",
    "clahe": "stage_4_clahe",
    "denoised": "stage_5_denoised",
    "final": "stage_6_final"
}


@router.get("/{document_id}/pages/{page_number}/stages")
def get_page_preprocessing_stages(
    document_id: int,
    page_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve real-time intermediate OpenCV preprocessing stage metadata for a page.
    Generates and caches stage assets securely on disk.
    """
    document = (
        db.query(Document.id)
        .filter(
            Document.id == document_id,
            Document.user_id == current_user.id
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )

    page = (
        db.query(HandwrittenPage)
        .filter(
            HandwrittenPage.document_id == document_id,
            HandwrittenPage.page_number == page_number
        )
        .first()
    )

    if not page or not page.original_image_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_number} not found."
        )

    orig_path = Path(page.original_image_path)
    if not orig_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original image file not found on disk."
        )

    doc_dir = HANDWRITTEN_BASE_DIR / str(document_id)
    stages_dir = doc_dir / "stages" / f"page_{page_number:03d}"

    raw_stages = generate_page_stages(orig_path, stages_dir)

    stages_with_urls = []
    for s in raw_stages:
        s_id = s["stage_id"]
        stages_with_urls.append({
            **s,
            "image_url": f"/handwritten/{document_id}/pages/{page_number}/stages/{s_id}/image",
            "thumb_url": f"/handwritten/{document_id}/pages/{page_number}/stages/{s_id}/image?thumb=true"
        })

    return {
        "document_id": document_id,
        "page_number": page_number,
        "original_url": f"/handwritten/{document_id}/pages/{page_number}/stages/original/image",
        "final_url": f"/handwritten/{document_id}/pages/{page_number}/stages/final/image",
        "stages": stages_with_urls
    }


@router.get("/{document_id}/pages/{page_number}/stages/{stage_id}/image")
def get_page_stage_image(
    document_id: int,
    page_number: int,
    stage_id: str,
    thumb: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Serve an intermediate preprocessing stage image or thumbnail.
    Enforces JWT authentication and tenant document ownership.
    """
    if stage_id not in STAGE_FILE_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid stage '{stage_id}'. Must be one of: {list(STAGE_FILE_MAP.keys())}"
        )

    document = (
        db.query(Document.id)
        .filter(
            Document.id == document_id,
            Document.user_id == current_user.id
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )

    page = (
        db.query(HandwrittenPage)
        .filter(
            HandwrittenPage.document_id == document_id,
            HandwrittenPage.page_number == page_number
        )
        .first()
    )

    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_number} not found."
        )

    doc_dir = HANDWRITTEN_BASE_DIR / str(document_id)
    stages_dir = doc_dir / "stages" / f"page_{page_number:03d}"
    base_name = STAGE_FILE_MAP[stage_id]
    target_filename = f"{base_name}_thumb.png" if thumb else f"{base_name}.png"
    target_path = stages_dir / target_filename

    if not target_path.exists():
        orig_path = Path(page.original_image_path)
        if not orig_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Original image missing."
            )
        generate_page_stages(orig_path, stages_dir)

    if not target_path.exists():
        fallback = stages_dir / f"{base_name}.png"
        if fallback.exists():
            target_path = fallback
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stage image for '{stage_id}' could not be generated."
            )

    return FileResponse(
        path=str(target_path),
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=3600"}
    )


@router.delete("/{document_id}")
def delete_handwritten_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a handwritten document, its physical pages, and database records.
    """
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == current_user.id,
            Document.is_handwritten == True
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Handwritten document not found."
        )

    # 1. Clean up file directory on disk
    doc_dir = HANDWRITTEN_BASE_DIR / str(document.id)
    if doc_dir.exists():
        import shutil
        try:
            shutil.rmtree(doc_dir)
        except Exception as error:
            logger.warning(f"Failed to delete disk directory {doc_dir}: {error}")

    # 2. Delete document chunks (if any were created)
    db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document.id
    ).delete(synchronize_session=False)

    # 3. Delete handwritten pages
    db.query(HandwrittenPage).filter(
        HandwrittenPage.document_id == document.id
    ).delete(synchronize_session=False)

    # 3b. Delete analysis records if any
    try:
        from app.models.handwritten_analysis import (
            HandwrittenSummary,
            HandwrittenConcept,
            HandwrittenQuizSet,
            HandwrittenFlashcardSet,
            HandwrittenChatSession
        )
        db.query(HandwrittenSummary).filter(HandwrittenSummary.document_id == document.id).delete(synchronize_session=False)
        db.query(HandwrittenConcept).filter(HandwrittenConcept.document_id == document.id).delete(synchronize_session=False)
        db.query(HandwrittenQuizSet).filter(HandwrittenQuizSet.document_id == document.id).delete(synchronize_session=False)
        db.query(HandwrittenFlashcardSet).filter(HandwrittenFlashcardSet.document_id == document.id).delete(synchronize_session=False)
        db.query(HandwrittenChatSession).filter(HandwrittenChatSession.document_id == document.id).delete(synchronize_session=False)
    except Exception as cleanup_err:
        logger.warning(f"Could not delete analysis records for doc #{document.id}: {cleanup_err}")

    # 4. Delete document record
    db.delete(document)
    db.commit()

    return {
        "message": "Handwritten document deleted successfully.",
        "document_id": document_id
    }


@router.get("/{document_id}/subject")
def get_document_subject_endpoint(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the current academic subject and available subjects for a document."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {
        "document_id": doc.id,
        "subject": doc.subject or "Humanities & General",
        "available_subjects": ACADEMIC_SUBJECTS
    }


@router.patch("/{document_id}/subject")
def update_document_subject_endpoint(
    document_id: int,
    req: SubjectUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Manually update the academic subject for a document."""
    try:
        updated_subject = set_document_subject(document_id, current_user.id, req.subject, db)
        return {
            "document_id": document_id,
            "subject": updated_subject,
            "message": "Subject updated successfully."
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{document_id}/subject/detect")
def auto_detect_subject_endpoint(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Automatically detect and assign the academic subject for a document."""
    try:
        detected_subject = auto_detect_and_set_subject(document_id, current_user.id, db)
        return {
            "document_id": document_id,
            "subject": detected_subject,
            "message": f"Subject auto-detected as '{detected_subject}'."
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


class CorrectionReviewRequest(BaseModel):
    action: str  # "accept" | "reject" | "revert"


@router.patch("/{document_id}/pages/{page_number}/corrections/{correction_id}")
def update_page_correction_status(
    document_id: int,
    page_number: int,
    correction_id: str,
    req: CorrectionReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Accept, reject, or revert an individual technical OCR recovery suggestion.
    Auditable and reversible: updates edited_transcription while strictly preserving raw_transcription.
    """
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    page = db.query(HandwrittenPage).filter(
        HandwrittenPage.document_id == document_id,
        HandwrittenPage.page_number == page_number
    ).first()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found.")

    meta = dict(page.ocr_metadata or {})
    corrs = list(meta.get("technical_corrections", []))
    target_corr = next((c for c in corrs if c.get("id") == correction_id), None)
    if not target_corr:
        raise HTTPException(status_code=404, detail=f"Correction '{correction_id}' not found.")

    orig_text = target_corr.get("original_text", "")
    sugg_text = target_corr.get("suggested_text", "")
    current_status = target_corr.get("status", "suggested")
    action = req.action.lower()

    if action == "accept":
        target_corr["status"] = "accepted"
        if page.edited_transcription and orig_text in page.edited_transcription:
            page.edited_transcription = page.edited_transcription.replace(orig_text, sugg_text)
    elif action == "reject":
        target_corr["status"] = "rejected"
        if current_status == "accepted" and page.edited_transcription and sugg_text in page.edited_transcription:
            page.edited_transcription = page.edited_transcription.replace(sugg_text, orig_text)
    elif action == "revert":
        target_corr["status"] = "suggested"
        if current_status == "accepted" and page.edited_transcription and sugg_text in page.edited_transcription:
            page.edited_transcription = page.edited_transcription.replace(sugg_text, orig_text)
    else:
        raise HTTPException(status_code=400, detail="Action must be 'accept', 'reject', or 'revert'.")

    meta["technical_corrections"] = corrs
    page.ocr_metadata = meta
    db.commit()
    db.refresh(page)
    _update_document_full_text(doc, db)

    return {
        "message": f"Correction '{correction_id}' set to {action}ed.",
        "correction": target_corr,
        "page_number": page.page_number,
        "edited_transcription": page.edited_transcription
    }




