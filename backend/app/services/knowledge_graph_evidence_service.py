from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.handwritten_page import HandwrittenPage
from app.services.research.paper_analysis_service import compute_research_content_hash
from app.services.research.paper_section_service import (
    ChunkUnit,
    assemble_document_chunks,
    build_section_hierarchy,
    is_toc_chunk,
)


_PAGE_BANNER_RE = re.compile(r"---\s*(?:Handwritten\s+)?Page\s+\d+\s*---", re.IGNORECASE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n{1,}")
_MULTISPACE_RE = re.compile(r"\s+")


@dataclass
class SentenceSpan:
    """Normalized sentence unit linked directly to its source chunk, page, and section."""

    index: int
    chunk_id: Optional[int]
    chunk_index: int
    page: int
    section: Optional[str]
    text: str
    lower_text: str


def clean_excerpt_text(text: str, max_len: int = 280) -> str:
    """Clean OCR/PDF page markers and clamp excerpt length for readable evidence UI."""
    cleaned = _PAGE_BANNER_RE.sub(" ", text or "")
    cleaned = _MULTISPACE_RE.sub(" ", cleaned).strip(" \t\r\n-•|")
    if len(cleaned) <= max_len:
        return cleaned
    clipped = cleaned[: max_len - 3].rsplit(" ", 1)[0].strip()
    return f"{clipped or cleaned[: max_len - 3]}..."


def assemble_substantive_document_units(
    document: Document,
    db: Session,
) -> Tuple[List[ChunkUnit], List[ChunkUnit], List[Dict[str, Any]], int, str]:
    """
    Reuse Cognidocs unified chunk assembly (printed, handwritten, mixed) read-only,
    filter TOC/empty noise, build section hierarchy, and compute deterministic content hash.
    """
    raw_units, pages_count = assemble_document_chunks(document, db)

    # Support mixed documents that combine DocumentChunk rows with additional HandwrittenPage rows
    hw_pages = (
        db.query(HandwrittenPage)
        .filter(HandwrittenPage.document_id == document.id)
        .order_by(HandwrittenPage.page_number.asc())
        .all()
    )
    if hw_pages:
        existing_pages = {int(u.page or 1) for u in raw_units}
        next_idx = max((u.chunk_index for u in raw_units), default=-1) + 1
        for hwp in hw_pages:
            hw_text = (hwp.edited_transcription or hwp.raw_transcription or "").strip()
            pnum = max(1, int(hwp.page_number or 1))
            if hw_text and (pnum not in existing_pages or document.is_handwritten and not raw_units):
                raw_units.append(
                    ChunkUnit(
                        chunk_id=None,
                        chunk_index=next_idx,
                        page=pnum,
                        content=hw_text,
                        section_title=None,
                        normalized_role="body",
                        embedding=None,
                    )
                )
                next_idx += 1
                pages_count = max(pages_count, pnum)

    content_hash = compute_research_content_hash(document, raw_units)

    substantive_units: List[ChunkUnit] = []
    for unit in raw_units:
        text = (unit.content or "").strip()
        if len(text) < 20:
            continue
        if is_toc_chunk(text):
            continue
        substantive_units.append(unit)

    if not substantive_units and raw_units:
        # Fallback for very short notes (e.g., compact handwritten snippets)
        substantive_units = [u for u in raw_units if (u.content or "").strip()]

    section_hierarchy = build_section_hierarchy(substantive_units or raw_units)
    return raw_units, substantive_units, section_hierarchy, pages_count, content_hash


def build_sentence_spans(units: Sequence[ChunkUnit]) -> List[SentenceSpan]:
    """Split substantive chunks into clean sentence spans preserving chunk/page/section provenance."""
    spans: List[SentenceSpan] = []
    seen_idx = 0
    for unit in units:
        cleaned_chunk = _PAGE_BANNER_RE.sub("\n", unit.content or "")
        parts = _SENTENCE_SPLIT_RE.split(cleaned_chunk)
        for raw_part in parts:
            sent = _MULTISPACE_RE.sub(" ", raw_part).strip()
            if len(sent) < 12:
                continue
            alpha_chars = sum(1 for ch in sent if ch.isalpha())
            if alpha_chars < 6:
                continue
            spans.append(
                SentenceSpan(
                    index=seen_idx,
                    chunk_id=unit.chunk_id,
                    chunk_index=unit.chunk_index,
                    page=max(1, int(unit.page or 1)),
                    section=unit.section_title,
                    text=sent,
                    lower_text=sent.lower(),
                )
            )
            seen_idx += 1
    return spans


def build_term_pattern(term: str) -> re.Pattern:
    """Build a word-boundary matcher resilient to hyphen/space variation."""
    tokens = [re.escape(tok) for tok in re.split(r"[\s\-]+", (term or "").strip().lower()) if tok]
    if not tokens:
        return re.compile(r"(?!x)x")
    body = r"[\s\-]+".join(tokens)
    return re.compile(rf"(?<![a-z0-9]){body}(?![a-z0-9])", re.IGNORECASE)


def find_term_matches_in_text(terms: Sequence[str], text: str) -> bool:
    """Return True if any term or alias occurs cleanly in `text`."""
    if not text:
        return False
    lowered = text.lower()
    for term in terms:
        clean = (term or "").strip()
        if not clean:
            continue
        if len(clean) <= 4 or "-" in clean or " " in clean:
            if build_term_pattern(clean).search(lowered):
                return True
        else:
            if clean.lower() in lowered:
                return True
    return False


_INDEX_STOPWORDS: Set[str] = {
    "the", "a", "an", "and", "or", "of", "in", "to", "for", "with", "on", "at",
    "by", "from", "as", "is", "are", "was", "were", "be", "been", "that", "this",
    "it", "into", "over", "under", "within", "between",
}


def build_sentence_inverted_index(spans: Sequence[SentenceSpan]) -> Dict[str, List[int]]:
    """Build a lightweight in-memory token index over sentence spans for fast candidate filtering."""
    index: Dict[str, List[int]] = {}
    for i, span in enumerate(spans):
        tokens = set(re.findall(r"[a-z0-9\-]{2,}", span.lower_text))
        for tok in tokens:
            lst = index.get(tok)
            if lst is None:
                index[tok] = [i]
            else:
                lst.append(i)
    return index


def find_entity_evidence(
    label: str,
    aliases: Sequence[str],
    spans: Sequence[SentenceSpan],
    units: Sequence[ChunkUnit],
    max_items: int = 4,
    sentence_index: Optional[Dict[str, List[int]]] = None,
) -> Tuple[List[Dict[str, Any]], List[int]]:
    """Collect grounded `EvidenceRef` dicts and source pages for a node label/aliases."""
    terms = [label, *[a for a in aliases if a and a.lower() != label.lower()]]
    patterns = [build_term_pattern(t) for t in terms if (t or "").strip()]
    if not patterns:
        return [], []

    evidence: List[Dict[str, Any]] = []
    seen_keys: Set[Tuple[Optional[int], int, str]] = set()
    pages: Set[int] = set()

    # If inverted index provided, evaluate only matching candidate spans first
    candidate_spans: Optional[List[SentenceSpan]] = None
    if sentence_index is not None and spans:
        cand_indices: Set[int] = set()
        for term in terms:
            words = [w for w in re.findall(r"[a-z0-9\-]{2,}", term.lower()) if w not in _INDEX_STOPWORDS and len(w) >= 2]
            if words:
                sorted_words = sorted(words, key=lambda w: len(sentence_index.get(w, [])))
                matched = set(sentence_index.get(sorted_words[0], []))
                for w in sorted_words[1:]:
                    matched &= set(sentence_index.get(w, []))
                cand_indices.update(matched)
            else:
                raw_words = re.findall(r"[a-z0-9\-]+", term.lower())
                for rw in raw_words:
                    cand_indices.update(sentence_index.get(rw, []))
        if cand_indices:
            candidate_spans = [spans[i] for i in sorted(cand_indices) if 0 <= i < len(spans)]

    scan_target = candidate_spans if (candidate_spans is not None and candidate_spans) else spans

    for span in scan_target:
        if any(pat.search(span.lower_text) for pat in patterns):
            excerpt = clean_excerpt_text(span.text, max_len=260)
            key = (span.chunk_id, span.page, excerpt[:80])
            if key not in seen_keys:
                seen_keys.add(key)
                pages.add(span.page)
                evidence.append(
                    {
                        "chunk_id": span.chunk_id,
                        "page": span.page,
                        "section": span.section,
                        "excerpt": excerpt,
                    }
                )
            if len(evidence) >= max_items:
                break

    # If candidate span filtering missed (e.g. edge case token split), fallback to full spans
    if not evidence and candidate_spans is not None and len(candidate_spans) < len(spans):
        for span in spans:
            if any(pat.search(span.lower_text) for pat in patterns):
                excerpt = clean_excerpt_text(span.text, max_len=260)
                key = (span.chunk_id, span.page, excerpt[:80])
                if key not in seen_keys:
                    seen_keys.add(key)
                    pages.add(span.page)
                    evidence.append(
                        {
                            "chunk_id": span.chunk_id,
                            "page": span.page,
                            "section": span.section,
                            "excerpt": excerpt,
                        }
                    )
                if len(evidence) >= max_items:
                    break

    if not evidence:
        # Fallback to full chunk scan in case term spanned line breaks weirdly
        for unit in units:
            cleaned = clean_excerpt_text(unit.content or "", max_len=260)
            if any(pat.search(cleaned.lower()) for pat in patterns):
                page = max(1, int(unit.page or 1))
                pages.add(page)
                evidence.append(
                    {
                        "chunk_id": unit.chunk_id,
                        "page": page,
                        "section": unit.section_title,
                        "excerpt": cleaned,
                    }
                )
                if len(evidence) >= max_items:
                    break

    return evidence, sorted(pages)


def find_pair_evidence(
    src_terms: Sequence[str],
    tgt_terms: Sequence[str],
    spans: Sequence[SentenceSpan],
    units: Sequence[ChunkUnit],
    max_items: int = 4,
    src_span_indices: Optional[Sequence[int]] = None,
    tgt_span_indices: Optional[Sequence[int]] = None,
) -> Dict[str, Any]:
    """
    Locate concrete shared evidence linking subject and object:
      - same-sentence matches (strongest)
      - adjacent sentence window (<= 2 sentences apart within same chunk)
      - same-chunk co-occurrence (weakest structural co-occurrence)
    When `src_span_indices` and `tgt_span_indices` are passed, skips full regex scanning.
    """
    if src_span_indices is None or tgt_span_indices is None:
        src_patterns = [build_term_pattern(t) for t in src_terms if (t or "").strip()]
        tgt_patterns = [build_term_pattern(t) for t in tgt_terms if (t or "").strip()]
        if not src_patterns or not tgt_patterns:
            return {
                "evidence": [],
                "source_pages": [],
                "min_distance": 999,
                "same_sentence_count": 0,
                "shared_chunk_count": 0,
                "spans_matched": [],
            }
        resolved_src = [i for i, s in enumerate(spans) if any(p.search(s.lower_text) for p in src_patterns)] if src_span_indices is None else list(src_span_indices)
        resolved_tgt = [i for i, s in enumerate(spans) if any(p.search(s.lower_text) for p in tgt_patterns)] if tgt_span_indices is None else list(tgt_span_indices)
    else:
        resolved_src = list(src_span_indices)
        resolved_tgt = list(tgt_span_indices)

    if not resolved_src or not resolved_tgt:
        return {
            "evidence": [],
            "source_pages": [],
            "min_distance": 999,
            "same_sentence_count": 0,
            "shared_chunk_count": 0,
            "spans_matched": [],
        }

    same_sent = sorted(set(resolved_src) & set(resolved_tgt))
    min_dist = 0 if same_sent else 999

    matched_items: List[Tuple[int, SentenceSpan, str]] = []
    for idx in same_sent:
        sp = spans[idx]
        matched_items.append((0, sp, clean_excerpt_text(sp.text, max_len=280)))

    # Adjacent sentences within same chunk
    if len(matched_items) < max_items and resolved_src and resolved_tgt:
        tgt_set = set(resolved_tgt)
        for s_idx in resolved_src:
            s_span = spans[s_idx]
            for offset in (-2, -1, 1, 2):
                n_idx = s_idx + offset
                if n_idx in tgt_set and 0 <= n_idx < len(spans):
                    t_span = spans[n_idx]
                    if t_span.chunk_index == s_span.chunk_index:
                        dist = abs(offset)
                        min_dist = min(min_dist, dist)
                        first, second = (s_span, t_span) if s_idx < n_idx else (t_span, s_span)
                        combined = clean_excerpt_text(f"{first.text} {second.text}", max_len=300)
                        matched_items.append((dist, first, combined))

    # Same-chunk fallback if still empty
    shared_chunks: Set[int] = set()
    src_chunks = {spans[i].chunk_index for i in resolved_src if 0 <= i < len(spans)}
    tgt_chunks = {spans[i].chunk_index for i in resolved_tgt if 0 <= i < len(spans)}
    shared_chunks = src_chunks & tgt_chunks

    if not matched_items and shared_chunks:
        min_dist = 3
        for unit in units:
            if unit.chunk_index in shared_chunks:
                s_lines = [spans[i].text for i in resolved_src if 0 <= i < len(spans) and spans[i].chunk_index == unit.chunk_index]
                t_lines = [spans[i].text for i in resolved_tgt if 0 <= i < len(spans) and spans[i].chunk_index == unit.chunk_index]
                joined = f"{s_lines[0]} ... {t_lines[0]}" if (s_lines and t_lines) else (unit.content or "")
                matched_items.append(
                    (
                        3,
                        SentenceSpan(
                            index=-1,
                            chunk_id=unit.chunk_id,
                            chunk_index=unit.chunk_index,
                            page=max(1, int(unit.page or 1)),
                            section=unit.section_title,
                            text=joined,
                            lower_text=joined.lower(),
                        ),
                        clean_excerpt_text(joined, max_len=300),
                    )
                )
                if len(matched_items) >= max_items:
                    break

    matched_items.sort(key=lambda row: (row[0], row[1].page, row[1].index))
    evidence: List[Dict[str, Any]] = []
    seen_excerpts: Set[str] = set()
    pages: Set[int] = set()
    raw_texts: List[str] = []

    for _, sp, excerpt in matched_items:
        sig = excerpt[:90].lower()
        if sig in seen_excerpts:
            continue
        seen_excerpts.add(sig)
        page = max(1, int(sp.page or 1))
        pages.add(page)
        raw_texts.append(sp.text)
        evidence.append(
            {
                "chunk_id": sp.chunk_id,
                "page": page,
                "section": sp.section,
                "excerpt": excerpt,
            }
        )
        if len(evidence) >= max_items:
            break

    return {
        "evidence": evidence,
        "source_pages": sorted(pages),
        "min_distance": min_dist,
        "same_sentence_count": len(same_sent),
        "shared_chunk_count": max(len(shared_chunks), 1 if evidence else 0),
        "spans_matched": raw_texts,
    }


def sanitize_evidence_list(
    evidence_list: Sequence[Dict[str, Any]],
    valid_chunk_ids: Set[Optional[int]],
    max_page: int,
) -> List[Dict[str, Any]]:
    """Ensure every EvidenceRef has non-empty excerpt and valid page/chunk bounds."""
    cleaned: List[Dict[str, Any]] = []
    seen: Set[Tuple[Optional[int], int, str]] = set()
    for ev in evidence_list or []:
        excerpt = clean_excerpt_text(str(ev.get("excerpt") or ""), max_len=300)
        if len(excerpt) < 8:
            continue
        cid = ev.get("chunk_id")
        if cid is not None and valid_chunk_ids and cid not in valid_chunk_ids:
            cid = None
        page = int(ev.get("page") or 1)
        if page < 1:
            page = 1
        elif max_page > 0 and page > max_page:
            page = max_page
        key = (cid, page, excerpt[:70].lower())
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(
            {
                "chunk_id": cid,
                "page": page,
                "section": ev.get("section"),
                "excerpt": excerpt,
            }
        )
    return cleaned

