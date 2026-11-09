import hashlib
import json
import logging
import math
import re
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_comparison import DocumentComparison
from app.models.handwritten_page import HandwrittenPage
from app.services.embedding_services import generate_embedding
from app.services.similarity_service import cosine_similarity
from app.services.handwriting.handwritten_source_service import (
    get_document_transcription_source,
    sync_handwritten_chunks_and_embeddings,
    chunk_text_by_paragraphs
)
from app.services.handwriting.ollama_client import query_ollama, extract_json_from_text, OllamaError
from app.services.text_processing_service import clean_text, chunk_text, detect_chunk_category

logger = logging.getLogger(__name__)

# Configurable semantic comparison thresholds
SIMILAR_THRESHOLD = 0.88
MODIFIED_THRESHOLD = 0.68


class ComparisonChunk:
    """Internal normalized chunk representation for semantic alignment."""
    def __init__(
        self,
        chunk_id: str,
        content: str,
        page_number: int,
        category: Optional[str] = None,
        embedding: Optional[List[float]] = None
    ):
        self.chunk_id = chunk_id
        self.content = content.strip()
        self.page_number = page_number or 1
        self.category = category or "General"
        self.clean_text = re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', '', content.lower())).strip()
        self.embedding = embedding or []
        self.magnitude = math.sqrt(sum(x * x for x in self.embedding)) if self.embedding else 0.0


def compute_content_hash(text: str) -> str:
    """Deterministic SHA-256 hash of document text content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""


def extract_topic_title(text: str, default: str = "Key Concept") -> str:
    """
    Extract a concise, readable title or topic heading from text snippet.
    """
    cleaned = text.strip()
    # Check for markdown heading (# Title or ## Title)
    heading_match = re.search(r'^#{1,3}\s*([^\n\r]+)', cleaned, re.MULTILINE)
    if heading_match:
        title = heading_match.group(1).strip()
        if len(title) > 4:
            return title[:60]

    # Check for leading "1. Title" or "A. Title"
    numbered_match = re.search(r'^(?:[0-9]+|[A-Z])[\.\:]\s*([^\n\r]+)', cleaned, re.MULTILINE)
    if numbered_match:
        title = numbered_match.group(1).strip()
        if len(title) > 4:
            return title[:60]

    # Fallback to the first sentence or first 60 chars
    first_sentence = re.split(r'[.!?\n]', cleaned)[0].strip()
    if 5 <= len(first_sentence) <= 60:
        return first_sentence
    elif len(first_sentence) > 60:
        return first_sentence[:57].rsplit(' ', 1)[0] + "..."
    return default


def split_content_into_comparison_units(full_text: str, max_chunk_chars: int = 600) -> List[str]:
    """
    Split text into logical, cohesive comparison units by paragraphs.
    If a paragraph exceeds max_chunk_chars, split on sentence boundaries.
    """
    raw_paragraphs = [p.strip() for p in re.split(r'\n\s*\n', full_text) if p.strip()]
    if not raw_paragraphs:
        raw_paragraphs = [p.strip() for p in full_text.splitlines() if p.strip()]

    units = []
    for para in raw_paragraphs:
        if len(para) <= max_chunk_chars:
            units.append(para)
        else:
            sentences = re.split(r'(?<=[.!?])\s+', para)
            current = []
            curr_len = 0
            for s in sentences:
                if curr_len + len(s) > max_chunk_chars and current:
                    units.append(" ".join(current).strip())
                    current = [s]
                    curr_len = len(s)
                else:
                    current.append(s)
                    curr_len += len(s) + 1
            if current:
                units.append(" ".join(current).strip())
    return units if units else ([full_text.strip()] if full_text.strip() else [])


def get_document_chunks_for_comparison(
    document: Document,
    db: Session
) -> Tuple[List[ComparisonChunk], str]:
    """
    Extract and return canonical ComparisonChunk objects with 384-dimensional embeddings
    and accurate page references for any document (PDF, DOCX, TXT, or Handwritten).
    Also returns the canonical full text representation for content hashing.
    """
    # CASE 1: Handwritten Document
    if document.is_handwritten:
        source_data = get_document_transcription_source(document.id, db)
        if not source_data["has_transcription"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document '{document.filename}' does not yet have usable extracted text for comparison."
            )

        full_text = source_data["full_text"]
        chunks = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.chunk_index.asc())
            .all()
        )

        # If chunks or embeddings are missing, rebuild them
        if not chunks or any(not c.embedding for c in chunks):
            sync_handwritten_chunks_and_embeddings(document.id, db)
            chunks = (
                db.query(DocumentChunk)
                .filter(DocumentChunk.document_id == document.id)
                .order_by(DocumentChunk.chunk_index.asc())
                .all()
            )

        comparison_chunks: List[ComparisonChunk] = []
        for idx, c in enumerate(chunks):
            if not c.content or not c.content.strip():
                continue
            comparison_chunks.append(
                ComparisonChunk(
                    chunk_id=f"doc_{document.id}_chunk_{idx}",
                    content=c.content,
                    page_number=c.page_number or 1,
                    category=c.category or "Handwritten Notes",
                    embedding=c.embedding
                )
            )

        if not comparison_chunks:
            # Fallback chunking from full text
            text_chunks = split_content_into_comparison_units(full_text)
            for idx, tc in enumerate(text_chunks):
                emb = generate_embedding(tc)
                comparison_chunks.append(
                    ComparisonChunk(
                        chunk_id=f"doc_{document.id}_syn_{idx}",
                        content=tc,
                        page_number=1,
                        category="Handwritten Notes",
                        embedding=emb
                    )
                )

        return comparison_chunks, full_text

    # CASE 2: Standard Document (PDF / DOCX / TXT)
    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.chunk_index.asc())
        .all()
    )

    full_text = document.extracted_text or ""
    if not full_text and chunks:
        full_text = "\n\n".join(c.content for c in chunks if c.content)

    if not full_text.strip() and not chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document '{document.filename}' contains no extracted text to compare."
        )

    # If chunks or embeddings do not exist or if there's only 1 chunk but multiple paragraphs
    text_units = split_content_into_comparison_units(full_text)
    if not chunks or (len(chunks) <= 1 and len(text_units) > 1):
        comparison_chunks = []
        for idx, unit_str in enumerate(text_units):
            if not unit_str.strip():
                continue
            cat = detect_chunk_category(unit_str)
            emb = generate_embedding(unit_str)
            comparison_chunks.append(
                ComparisonChunk(
                    chunk_id=f"doc_{document.id}_unit_{idx}",
                    content=unit_str,
                    page_number=1,
                    category=cat,
                    embedding=emb
                )
            )
        return comparison_chunks, full_text

    # Load from existing DB chunks
    comparison_chunks = []
    for idx, c in enumerate(chunks):
        if not c.content or not c.content.strip():
            continue
        emb = c.embedding
        if not emb:
            emb = generate_embedding(c.content)
            c.embedding = emb
            db.add(c)
        comparison_chunks.append(
            ComparisonChunk(
                chunk_id=f"doc_{document.id}_chunk_{idx}",
                content=c.content,
                page_number=c.page_number or 1,
                category=c.category or "General",
                embedding=emb
            )
        )
    db.commit()
    return comparison_chunks, full_text


def summarize_change_difference(text_a: str, text_b: str) -> str:
    """
    Generate a concise natural-language explanation of what modified between two text chunks.
    """
    words_a = set(re.findall(r'\b[a-zA-Z0-9_\-]{3,}\b', text_a.lower()))
    words_b = set(re.findall(r'\b[a-zA-Z0-9_\-]{3,}\b', text_b.lower()))

    added_terms = list(words_b - words_a)[:4]
    removed_terms = list(words_a - words_b)[:4]

    parts = []
    if added_terms:
        parts.append(f"Document B introduces: {', '.join(added_terms)}")
    if removed_terms:
        parts.append(f"omitted from Document A: {', '.join(removed_terms)}")

    if parts:
        return "; ".join(parts) + "."
    return "Content updated with revised terminology and modified phrasing."


def align_and_classify_documents(
    chunks_a: List[ComparisonChunk],
    chunks_b: List[ComparisonChunk]
) -> Dict[str, Any]:
    """
    Perform semantic alignment between chunks of Document A and Document B.
    Classifies aligned units into SIMILAR (or UNCHANGED), MODIFIED, ADDED, and REMOVED.
    """
    if not chunks_a and not chunks_b:
        return {
            "statistics": {"total_units": 0, "similar": 0, "modified": 0, "added": 0, "removed": 0},
            "similarities": [],
            "modified": [],
            "added": [],
            "removed": []
        }

    # If Document A is empty and B has content -> All B chunks are ADDED
    if not chunks_a and chunks_b:
        added_list = [
            {
                "id": f"add-{idx+1}",
                "title": extract_topic_title(b.content, f"New Section {idx+1}"),
                "category": b.category,
                "document_b_text": b.content,
                "document_b_page": b.page_number
            }
            for idx, b in enumerate(chunks_b)
        ]
        return {
            "statistics": {"total_units": len(chunks_b), "similar": 0, "modified": 0, "added": len(chunks_b), "removed": 0},
            "similarities": [],
            "modified": [],
            "added": added_list,
            "removed": []
        }

    # If Document B is empty and A has content -> All A chunks are REMOVED
    if chunks_a and not chunks_b:
        removed_list = [
            {
                "id": f"rem-{idx+1}",
                "title": extract_topic_title(a.content, f"Removed Section {idx+1}"),
                "category": a.category,
                "document_a_text": a.content,
                "document_a_page": a.page_number
            }
            for idx, a in enumerate(chunks_a)
        ]
        return {
            "statistics": {"total_units": len(chunks_a), "similar": 0, "modified": 0, "added": 0, "removed": len(chunks_a)},
            "similarities": [],
            "modified": [],
            "added": [],
            "removed": removed_list
        }

    # Compute pairwise similarities
    # Score candidates: (score, idx_a, idx_b)
    candidates: List[Tuple[float, int, int]] = []
    for i, a in enumerate(chunks_a):
        for j, b in enumerate(chunks_b):
            # Check exact or normalized clean match first
            if a.clean_text == b.clean_text and len(a.clean_text) > 10:
                sim = 1.0
            elif a.embedding and b.embedding:
                sim = cosine_similarity(a.embedding, b.embedding, a.magnitude)
            else:
                sim = 0.0

            if sim >= MODIFIED_THRESHOLD:
                candidates.append((sim, i, j))

    # Sort candidates descending by similarity score
    candidates.sort(key=lambda x: x[0], reverse=True)

    matched_a = set()
    matched_b = set()

    similarities = []
    modified = []

    # Greedily match maximum similarity pairs
    for sim, i, j in candidates:
        if i in matched_a or j in matched_b:
            continue

        matched_a.add(i)
        matched_b.add(j)

        chunk_a = chunks_a[i]
        chunk_b = chunks_b[j]
        topic_title = extract_topic_title(chunk_b.content or chunk_a.content)

        if sim >= SIMILAR_THRESHOLD:
            # UNCHANGED / SIMILAR
            similarities.append({
                "id": f"sim-{len(similarities)+1}",
                "title": topic_title,
                "category": chunk_b.category if chunk_b.category != "General" else chunk_a.category,
                "document_a_text": chunk_a.content,
                "document_b_text": chunk_b.content,
                "document_a_page": chunk_a.page_number,
                "document_b_page": chunk_b.page_number,
                "similarity_score": round(sim, 3),
                "is_unchanged": sim >= 0.96 or (chunk_a.clean_text == chunk_b.clean_text)
            })
        else:
            # MODIFIED
            change_desc = summarize_change_difference(chunk_a.content, chunk_b.content)
            modified.append({
                "id": f"mod-{len(modified)+1}",
                "title": topic_title,
                "category": chunk_b.category if chunk_b.category != "General" else chunk_a.category,
                "change_description": change_desc,
                "document_a_text": chunk_a.content,
                "document_b_text": chunk_b.content,
                "document_a_page": chunk_a.page_number,
                "document_b_page": chunk_b.page_number,
                "similarity_score": round(sim, 3)
            })

    # Unmatched chunks in Document A -> REMOVED
    removed = []
    for i, a in enumerate(chunks_a):
        if i not in matched_a:
            removed.append({
                "id": f"rem-{len(removed)+1}",
                "title": extract_topic_title(a.content, f"Section {a.page_number}"),
                "category": a.category,
                "document_a_text": a.content,
                "document_a_page": a.page_number
            })

    # Unmatched chunks in Document B -> ADDED
    added = []
    for j, b in enumerate(chunks_b):
        if j not in matched_b:
            added.append({
                "id": f"add-{len(added)+1}",
                "title": extract_topic_title(b.content, f"Section {b.page_number}"),
                "category": b.category,
                "document_b_text": b.content,
                "document_b_page": b.page_number
            })

    total_units = len(similarities) + len(modified) + len(added) + len(removed)

    return {
        "statistics": {
            "total_units": total_units,
            "similar": len(similarities),
            "modified": len(modified),
            "added": len(added),
            "removed": len(removed)
        },
        "similarities": similarities,
        "modified": modified,
        "added": added,
        "removed": removed
    }


def generate_deterministic_comparison_summary(
    doc_a_name: str,
    doc_b_name: str,
    stats: Dict[str, int],
    similarities: List[Dict[str, Any]],
    modified: List[Dict[str, Any]],
    added: List[Dict[str, Any]],
    removed: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Produce a deterministic, grounded comparison synthesis when Ollama is unavailable
    or as a fast fallback.
    """
    total = stats.get("total_units", 0)
    sim_count = stats.get("similar", 0)
    mod_count = stats.get("modified", 0)
    add_count = stats.get("added", 0)
    rem_count = stats.get("removed", 0)

    if total == 0:
        summary_text = f"Both '{doc_a_name}' and '{doc_b_name}' contain minimal comparable text."
    elif sim_count == total:
        summary_text = (
            f"'{doc_b_name}' is semantically identical to '{doc_a_name}'. "
            f"All {sim_count} comparison units match across both documents with no detected modifications or omissions."
        )
    else:
        summary_text = (
            f"Comparison between '{doc_a_name}' and '{doc_b_name}' reveals {sim_count} shared/similar sections, "
            f"{mod_count} modified sections, {add_count} newly added sections, and {rem_count} omitted sections."
        )

    key_changes = [
        f"{m.get('title', 'Section')}: {m.get('change_description', 'Content modified between versions')}"
        for m in modified[:3]
    ]

    important_additions = [
        f"Page {a.get('document_b_page', 1)}: {a.get('title', 'Added content')} - {a.get('document_b_text', '')[:90]}..."
        for a in added[:3]
    ]

    important_removals = [
        f"Page {r.get('document_a_page', 1)}: {r.get('title', 'Removed content')} - {r.get('document_a_text', '')[:90]}..."
        for r in removed[:3]
    ]

    implications = (
        "Document B represents an evolved revision containing updated facts and newly introduced sections."
        if add_count > 0 or mod_count > 0
        else "Both documents maintain strong factual consistency with standard content alignment."
    )

    return {
        "summary": summary_text,
        "key_changes": key_changes,
        "important_additions": important_additions,
        "important_removals": important_removals,
        "implications": implications
    }


def generate_ai_comparison_summary(
    doc_a_name: str,
    doc_b_name: str,
    stats: Dict[str, int],
    similarities: List[Dict[str, Any]],
    modified: List[Dict[str, Any]],
    added: List[Dict[str, Any]],
    removed: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Generate an intelligent natural-language interpretation of the comparison evidence
    using local Ollama (Llama 3.2), strictly grounded in the supplied structured differences.
    """
    # If identical documents, return direct synthesis without unnecessary LLM overhead
    if stats.get("total_units", 0) > 0 and stats.get("similar", 0) == stats.get("total_units"):
        return generate_deterministic_comparison_summary(
            doc_a_name, doc_b_name, stats, similarities, modified, added, removed
        )

    # Prepare structured evidence payload
    evidence_payload = {
        "document_a": doc_a_name,
        "document_b": doc_b_name,
        "statistics": stats,
        "sample_similarities": [
            {"title": s["title"], "page_a": s.get("document_a_page"), "page_b": s.get("document_b_page")}
            for s in similarities[:4]
        ],
        "sample_modifications": [
            {
                "title": m["title"],
                "doc_a_excerpt": m.get("document_a_text", "")[:120],
                "doc_b_excerpt": m.get("document_b_text", "")[:120],
                "pages": f"A:p{m.get('document_a_page')} -> B:p{m.get('document_b_page')}"
            }
            for m in modified[:4]
        ],
        "sample_additions": [
            {"title": a["title"], "page_b": a.get("document_b_page"), "excerpt": a.get("document_b_text", "")[:120]}
            for a in added[:4]
        ],
        "sample_removals": [
            {"title": r["title"], "page_a": r.get("document_a_page"), "excerpt": r.get("document_a_text", "")[:120]}
            for r in removed[:4]
        ]
    }

    system_prompt = (
        "You are Cognidocs Document Comparison Engine, an objective academic AI assistant. "
        "Analyze the provided structured comparison evidence between Document A and Document B. "
        "Strictly ground all findings exclusively in the supplied evidence. Do not extrapolate outside knowledge. "
        "Return ONLY a valid JSON object matching the requested schema."
    )

    user_prompt = f"""Compare the two documents based strictly on this structured evidence:

EVIDENCE:
{json.dumps(evidence_payload, indent=2)}

Produce a JSON response with this exact structure:
{{
  "summary": "Concise executive overview (2-3 sentences) explaining how Document B compares to Document A, mentioning similarity count and key differences.",
  "key_changes": [
    "Specific change 1 with reference to Document A vs B",
    "Specific change 2"
  ],
  "important_additions": [
    "Key addition 1 introduced in Document B"
  ],
  "important_removals": [
    "Key concept 1 omitted or removed from Document A"
  ],
  "implications": "Brief 1-2 sentence interpretation of what these changes mean for the reader."
}}"""

    try:
        raw_response = query_ollama(
            prompt=user_prompt,
            system_prompt=system_prompt,
            format_json=True,
            temperature=0.15,
            timeout=30
        )
        parsed = extract_json_from_text(raw_response)
        if isinstance(parsed, dict) and "summary" in parsed:
            return {
                "summary": str(parsed.get("summary", "")).strip(),
                "key_changes": list(parsed.get("key_changes", []))[:5],
                "important_additions": list(parsed.get("important_additions", []))[:5],
                "important_removals": list(parsed.get("important_removals", []))[:5],
                "implications": str(parsed.get("implications", "")).strip()
            }
    except Exception as e:
        logger.warning(f"Ollama comparison summary generation failed: {e}. Falling back to deterministic synthesis.")

    return generate_deterministic_comparison_summary(
        doc_a_name, doc_b_name, stats, similarities, modified, added, removed
    )


def compare_documents_service(
    document_a_id: int,
    document_b_id: int,
    user_id: int,
    db: Session,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Main entry point for comparing two documents belonging to the authenticated user.
    Enforces security isolation, semantic alignment, AI interpretation, and caching.
    """
    # 1. Validation: Prevent comparing a document with itself
    if document_a_id == document_b_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot compare a document with itself. Please select two different documents."
        )

    # 2. Authorization & Existence Check
    doc_a = (
        db.query(Document)
        .filter(Document.id == document_a_id, Document.user_id == user_id)
        .first()
    )
    if not doc_a:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document A (ID #{document_a_id}) was not found or access is denied."
        )

    doc_b = (
        db.query(Document)
        .filter(Document.id == document_b_id, Document.user_id == user_id)
        .first()
    )
    if not doc_b:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document B (ID #{document_b_id}) was not found or access is denied."
        )

    # 3. Content Extraction & Chunk Normalization
    chunks_a, text_a = get_document_chunks_for_comparison(doc_a, db)
    chunks_b, text_b = get_document_chunks_for_comparison(doc_b, db)

    hash_a = compute_content_hash(text_a)
    hash_b = compute_content_hash(text_b)

    # 4. Check Comparison Cache
    if not force_refresh:
        cached_record = (
            db.query(DocumentComparison)
            .filter(
                DocumentComparison.user_id == user_id,
                DocumentComparison.document_a_id == document_a_id,
                DocumentComparison.document_b_id == document_b_id,
                DocumentComparison.document_a_hash == hash_a,
                DocumentComparison.document_b_hash == hash_b
            )
            .first()
        )
        if cached_record and cached_record.comparison_result:
            result = dict(cached_record.comparison_result)
            result["cached"] = True
            return result

    # 5. Semantic Alignment & Classification
    alignment_data = align_and_classify_documents(chunks_a, chunks_b)

    # 6. AI Grounded Summary Generation
    ai_summary_data = generate_ai_comparison_summary(
        doc_a_name=doc_a.filename,
        doc_b_name=doc_b.filename,
        stats=alignment_data["statistics"],
        similarities=alignment_data["similarities"],
        modified=alignment_data["modified"],
        added=alignment_data["added"],
        removed=alignment_data["removed"]
    )

    # Compute page counts
    pages_a = max([c.page_number for c in chunks_a] or [1])
    pages_b = max([c.page_number for c in chunks_b] or [1])

    # 7. Assemble Structured Result
    comparison_response = {
        "document_a": {
            "id": doc_a.id,
            "filename": doc_a.filename,
            "document_type": doc_a.document_type,
            "is_handwritten": bool(doc_a.is_handwritten),
            "total_pages": pages_a,
            "chunk_count": len(chunks_a)
        },
        "document_b": {
            "id": doc_b.id,
            "filename": doc_b.filename,
            "document_type": doc_b.document_type,
            "is_handwritten": bool(doc_b.is_handwritten),
            "total_pages": pages_b,
            "chunk_count": len(chunks_b)
        },
        "summary": ai_summary_data.get("summary", ""),
        "key_changes": ai_summary_data.get("key_changes", []),
        "important_additions": ai_summary_data.get("important_additions", []),
        "important_removals": ai_summary_data.get("important_removals", []),
        "implications": ai_summary_data.get("implications", ""),
        "statistics": alignment_data["statistics"],
        "similarities": alignment_data["similarities"],
        "modified": alignment_data["modified"],
        "added": alignment_data["added"],
        "removed": alignment_data["removed"],
        "cached": False
    }

    # 8. Persist / Update Cache
    existing_record = (
        db.query(DocumentComparison)
        .filter(
            DocumentComparison.user_id == user_id,
            DocumentComparison.document_a_id == document_a_id,
            DocumentComparison.document_b_id == document_b_id
        )
        .first()
    )

    if existing_record:
        existing_record.document_a_hash = hash_a
        existing_record.document_b_hash = hash_b
        existing_record.comparison_result = comparison_response
    else:
        new_record = DocumentComparison(
            user_id=user_id,
            document_a_id=document_a_id,
            document_b_id=document_b_id,
            document_a_hash=hash_a,
            document_b_hash=hash_b,
            comparison_result=comparison_response
        )
        db.add(new_record)

    db.commit()

    return comparison_response
