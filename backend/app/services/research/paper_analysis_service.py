from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.research_paper_analysis import ResearchPaperAnalysis
from app.services.research.paper_detector import detect_research_paper
from app.services.research.paper_extraction_service import extract_structured_research_analysis
from app.services.research.paper_section_service import (
    ChunkUnit,
    assemble_document_chunks,
    build_section_hierarchy,
)

RESEARCH_ANALYSIS_VERSION = "phase1_v1"


def get_owned_document(db: Session, document_id: int, user_id: int) -> Document:
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == user_id)
        .first()
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    return doc


def compute_research_content_hash(document: Document, units: List[ChunkUnit]) -> str:
    """
    Compute deterministic SHA-256 hash over current effective document text +
    chunk layout so any re-upload, re-OCR, or manual edit invalidates stale cache.
    """
    hasher = hashlib.sha256()
    hasher.update((document.document_type or "").encode("utf-8", errors="ignore"))
    hasher.update(b"|")
    hasher.update(("1" if document.is_handwritten else "0").encode("utf-8"))
    hasher.update(b"|")
    for u in units:
        hasher.update(f"{u.chunk_index}:{u.page}:".encode("utf-8"))
        hasher.update((u.content or "").encode("utf-8", errors="ignore"))
        hasher.update(b"\n")
    if not units and document.extracted_text:
        hasher.update(document.extracted_text.encode("utf-8", errors="ignore"))
    return hasher.hexdigest()


def _count_sections(sections: List[Dict[str, Any]]) -> int:
    total = 0
    for s in sections or []:
        total += 1
        total += _count_sections(s.get("children", []))
    return total


def _serialize_analysis_row(
    row: ResearchPaperAnalysis,
    document: Document,
    pages_count: int,
    cached: bool,
    is_outdated: bool,
    cache_retrieval_ms: float = 0.0,
) -> Dict[str, Any]:
    timings = dict(row.timings or {})
    if cached:
        timings["cache_retrieval_ms"] = round(cache_retrieval_ms, 2)

    all_fields = []
    for sec in (row.basic_information, row.research_context, row.methodology, row.evaluation, row.conclusion):
        if isinstance(sec, dict):
            all_fields.extend(sec.values())
    populated = [f for f in all_fields if isinstance(f, dict) and f.get("fact_type") != "missing"]
    grounded = [f for f in populated if len(f.get("sources") or []) > 0]
    coverage = round(len(grounded) / len(populated), 2) if populated else 0.0

    return {
        "document_id": document.id,
        "document_filename": document.filename,
        "document_type": document.document_type,
        "is_handwritten": bool(document.is_handwritten),
        "content_hash": row.content_hash,
        "analysis_version": row.analysis_version,
        "status": row.status,
        "is_outdated": is_outdated,
        "cached": cached,
        "analysis_mode": row.analysis_mode,
        "pages_count": pages_count,
        "sections_count": _count_sections(row.sections or []),
        "evidence_count": len(row.evidence or {}),
        "evidence_coverage": coverage,
        "generated_at": row.updated_at.isoformat() if row.updated_at else (row.created_at.isoformat() if row.created_at else None),
        "paper_detection": row.paper_detection,
        "basic_information": row.basic_information,
        "research_context": row.research_context,
        "methodology": row.methodology,
        "evaluation": row.evaluation,
        "conclusion": row.conclusion,
        "sections": row.sections,
        "numerical_data": row.numerical_data,
        "tables_and_figures": row.tables_and_figures,
        "evidence": row.evidence,
        "timings": timings,
    }


def get_cached_research_analysis(
    db: Session,
    document_id: int,
    user_id: int,
) -> Dict[str, Any]:
    t0 = time.perf_counter()
    document = get_owned_document(db, document_id, user_id)
    row = (
        db.query(ResearchPaperAnalysis)
        .filter(
            ResearchPaperAnalysis.document_id == document.id,
            ResearchPaperAnalysis.user_id == user_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research paper analysis has not been generated for this document yet.",
        )

    units, pages_count = assemble_document_chunks(document, db)
    current_hash = compute_research_content_hash(document, units)
    is_outdated = (
        row.content_hash != current_hash
        or row.analysis_version != RESEARCH_ANALYSIS_VERSION
    )
    cache_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    return _serialize_analysis_row(
        row=row,
        document=document,
        pages_count=pages_count,
        cached=True,
        is_outdated=is_outdated,
        cache_retrieval_ms=cache_ms,
    )


def analyze_research_paper(
    db: Session,
    document_id: int,
    user_id: int,
    force_refresh: bool = False,
    classification_override: Optional[str] = None,
    skip_llm: bool = False,
) -> Dict[str, Any]:
    """
    Detect research paper structure and generate/return cached source-grounded analysis
    for an authenticated user's owned document.
    """
    t_total = time.perf_counter()
    document = get_owned_document(db, document_id, user_id)
    units, pages_count = assemble_document_chunks(document, db)
    current_hash = compute_research_content_hash(document, units)

    existing = (
        db.query(ResearchPaperAnalysis)
        .filter(
            ResearchPaperAnalysis.document_id == document.id,
            ResearchPaperAnalysis.user_id == user_id,
        )
        .first()
    )

    # Determine effective manual override
    if classification_override == "auto":
        effective_override: Optional[str] = None
    elif classification_override in {"research_paper", "non_research"}:
        effective_override = classification_override
    else:
        effective_override = existing.classification_override if existing else None

    if (
        existing
        and not force_refresh
        and existing.status == "completed"
        and existing.content_hash == current_hash
        and existing.analysis_version == RESEARCH_ANALYSIS_VERSION
        and existing.classification_override == effective_override
    ):
        cache_ms = round((time.perf_counter() - t_total) * 1000.0, 2)
        return _serialize_analysis_row(
            row=existing,
            document=document,
            pages_count=pages_count,
            cached=True,
            is_outdated=False,
            cache_retrieval_ms=cache_ms,
        )

    t_det = time.perf_counter()
    sections = build_section_hierarchy(units)
    full_text = "\n\n".join(u.content for u in units) if units else (document.extracted_text or "")
    detection = detect_research_paper(
        units=units,
        sections=sections,
        full_text=full_text,
        manual_override=effective_override,
    )
    detection_ms = round((time.perf_counter() - t_det) * 1000.0, 2)

    extracted = extract_structured_research_analysis(
        document_id=document.id,
        units=units,
        sections=sections,
        skip_llm=skip_llm,
    )

    total_ms = round((time.perf_counter() - t_total) * 1000.0, 2)
    timings = {
        "detection_ms": detection_ms,
        "extraction_ms": extracted["extraction_ms"],
        "llm_ms": extracted["llm_ms"],
        "total_ms": total_ms,
        "cache_retrieval_ms": 0.0,
    }

    if existing:
        existing.content_hash = current_hash
        existing.analysis_version = RESEARCH_ANALYSIS_VERSION
        existing.classification_override = effective_override
        existing.status = "completed"
        existing.analysis_mode = extracted["analysis_mode"]
        existing.paper_detection = detection
        existing.basic_information = extracted["basic_information"]
        existing.research_context = extracted["research_context"]
        existing.methodology = extracted["methodology"]
        existing.evaluation = extracted["evaluation"]
        existing.conclusion = extracted["conclusion"]
        existing.sections = sections
        existing.numerical_data = extracted["numerical_data"]
        existing.tables_and_figures = extracted["tables_and_figures"]
        existing.evidence = extracted["evidence"]
        existing.timings = timings
        row = existing
    else:
        row = ResearchPaperAnalysis(
            document_id=document.id,
            user_id=user_id,
            content_hash=current_hash,
            analysis_version=RESEARCH_ANALYSIS_VERSION,
            classification_override=effective_override,
            status="completed",
            analysis_mode=extracted["analysis_mode"],
            paper_detection=detection,
            basic_information=extracted["basic_information"],
            research_context=extracted["research_context"],
            methodology=extracted["methodology"],
            evaluation=extracted["evaluation"],
            conclusion=extracted["conclusion"],
            sections=sections,
            numerical_data=extracted["numerical_data"],
            tables_and_figures=extracted["tables_and_figures"],
            evidence=extracted["evidence"],
            timings=timings,
        )
        db.add(row)

    db.commit()
    db.refresh(row)

    return _serialize_analysis_row(
        row=row,
        document=document,
        pages_count=pages_count,
        cached=False,
        is_outdated=False,
        cache_retrieval_ms=0.0,
    )

