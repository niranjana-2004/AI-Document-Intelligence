import logging
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.user import User
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.handwritten_page import HandwrittenPage
from app.models.activity import ActivityLog
from app.services.handwriting.pdf_rasterizer import rasterize_document_to_images
from app.services.handwriting.image_preprocessor import preprocess_handwritten_image

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


@router.post("/upload")
async def upload_handwritten_document(
    file: UploadFile = File(...),
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

    # 4. Delete document record
    db.delete(document)
    db.commit()

    return {
        "message": "Handwritten document deleted successfully.",
        "document_id": document_id
    }
