from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.handwritten_page import HandwrittenPage
from app.services.text_processing_service import clean_text


@dataclass
class ChunkUnit:
    """Normalized document slice with preserved page, chunk ID, and section provenance."""
    chunk_id: Optional[int]
    chunk_index: int
    page: int
    content: str
    section_title: str = "Document Overview"
    normalized_role: str = "other"
    embedding: Any = None


_ROLE_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    ("abstract", re.compile(r"^(?:[ivxlcdm]+\.\s*)?abstract\b", re.IGNORECASE)),
    ("keywords", re.compile(r"^(?:keywords?|index\s+terms?)\b", re.IGNORECASE)),
    (
        "introduction",
        re.compile(r"^(?:\d+(?:\.\d+)*\.?\s+|[ivxlcdm]+\.\s+)?(?:introduction|overview|background)\b", re.IGNORECASE),
    ),
    (
        "related_work",
        re.compile(
            r"^(?:\d+(?:\.\d+)*\.?\s+|[ivxlcdm]+\.\s+)?(?:related\s+work|literature\s+(?:review|survey)|prior\s+work|state\s+of\s+the\s+art)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "methodology",
        re.compile(
            r"^(?:\d+(?:\.\d+)*\.?\s+|[ivxlcdm]+\.\s+)?(?:methodology|methods?|proposed\s+(?:method|approach|system|framework|model|architecture)|system\s+(?:architecture|design|workflow)|materials?\s+and\s+methods?|approach|implementation|design)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "experiments",
        re.compile(
            r"^(?:\d+(?:\.\d+)*\.?\s+|[ivxlcdm]+\.\s+)?(?:experiments?|experimental\s+(?:setup|design|evaluation|methodology)|dataset(?:s)?\s*(?:and\s+setup)?|evaluation\s+(?:setup|methodology))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "results",
        re.compile(
            r"^(?:\d+(?:\.\d+)*\.?\s+|[ivxlcdm]+\.\s+)?(?:results?|results?\s+and\s+discussion|findings?|performance\s+(?:analysis|evaluation)|empirical\s+evaluation|evaluation)\b",
            re.IGNORECASE,
        ),
    ),
    ("discussion", re.compile(r"^(?:\d+(?:\.\d+)*\.?\s+|[ivxlcdm]+\.\s+)?(?:discussion|limitations?|threats?\s+to\s+validity)\b", re.IGNORECASE)),
    (
        "conclusion",
        re.compile(
            r"^(?:\d+(?:\.\d+)*\.?\s+|[ivxlcdm]+\.\s+)?(?:conclusions?(?:\s+and\s+future\s+work)?|future\s+work|summary\s+and\s+conclusions?)\b",
            re.IGNORECASE,
        ),
    ),
    ("references", re.compile(r"^(?:\d+(?:\.\d+)*\.?\s+)?(?:references|bibliography|works\s+cited)\b", re.IGNORECASE)),
    ("acknowledgements", re.compile(r"^(?:acknowledg(?:e)?ments?|dedication|abbreviations?)\b", re.IGNORECASE)),
    ("appendix", re.compile(r"^(?:appendix(?:\s+[a-z0-9]+)?)\b", re.IGNORECASE)),
]

_STANDALONE_HEADINGS = {
    "abstract",
    "introduction",
    "related work",
    "literature review",
    "background",
    "methodology",
    "methods",
    "proposed methodology",
    "proposed approach",
    "proposed method",
    "proposed system",
    "system architecture",
    "experimental setup",
    "experiments",
    "results",
    "results and discussion",
    "performance analysis",
    "evaluation",
    "discussion",
    "limitations",
    "conclusion",
    "conclusions",
    "future work",
    "conclusion and future work",
    "conclusions and future work",
    "references",
    "bibliography",
    "acknowledgements",
    "acknowledgments",
}


def assemble_document_chunks(document: Document, db: Session) -> Tuple[List[ChunkUnit], int]:
    """
    Reassemble ordered chunk units from existing DB chunks (or fallback text/handwritten pages)
    preserving page numbers and chunk IDs without re-parsing files unnecessarily.
    """
    raw_chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.chunk_index.asc(), DocumentChunk.id.asc())
        .all()
    )

    units: List[ChunkUnit] = []
    if raw_chunks:
        for idx, ch in enumerate(raw_chunks):
            txt = clean_text(ch.content or "")
            if not txt:
                continue
            units.append(
                ChunkUnit(
                    chunk_id=ch.id,
                    chunk_index=ch.chunk_index if ch.chunk_index is not None else idx,
                    page=int(ch.page_number) if ch.page_number and int(ch.page_number) > 0 else 1,
                    content=txt,
                    embedding=ch.embedding,
                )
            )

    if not units and document.is_handwritten:
        hw_pages = (
            db.query(HandwrittenPage)
            .filter(HandwrittenPage.document_id == document.id)
            .order_by(HandwrittenPage.page_number.asc())
            .all()
        )
        for idx, page_row in enumerate(hw_pages):
            txt = clean_text((page_row.edited_transcription or page_row.raw_transcription or "").strip())
            if txt:
                units.append(
                    ChunkUnit(
                        chunk_id=None,
                        chunk_index=idx,
                        page=int(page_row.page_number or 1),
                        content=txt,
                    )
                )

    if not units and (document.extracted_text or "").strip():
        full_txt = clean_text(document.extracted_text or "")
        # Check for explicit handwritten/page markers before falling back to single block chunks
        page_blocks = re.split(r"---\s*Page\s+(\d+)\s*---\s*", full_txt)
        if len(page_blocks) >= 3:
            idx = 0
            i = 1
            while i + 1 < len(page_blocks):
                pnum = max(1, int(page_blocks[i]))
                ptext = clean_text(page_blocks[i + 1])
                if ptext:
                    units.append(ChunkUnit(chunk_id=None, chunk_index=idx, page=pnum, content=ptext))
                    idx += 1
                i += 2
        else:
            step = 1000
            for idx, start in enumerate(range(0, len(full_txt), step)):
                piece = full_txt[start : start + step].strip()
                if piece:
                    units.append(ChunkUnit(chunk_id=None, chunk_index=idx, page=1, content=piece))

    max_page = max((u.page for u in units), default=1)
    return units, max_page


def normalize_section_role(heading: str) -> str:
    cleaned = re.sub(r"^#{1,4}\s*", "", heading.strip())
    for role, pat in _ROLE_PATTERNS:
        if pat.match(cleaned):
            return role
    lower = cleaned.lower()
    if "dataset" in lower or "preprocessing" in lower or "algorithm" in lower or "architecture" in lower:
        return "methodology"
    if "metric" in lower or "baseline" in lower or "ablation" in lower or "comparison" in lower:
        return "results"
    if "problem" in lower or "motivation" in lower or "objective" in lower:
        return "introduction"
    if "limitation" in lower or "future" in lower:
        return "conclusion"
    return "other"


def _is_noise_or_toc_line(line: str, in_toc_block: bool) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    # Dotted Table of Contents leaders or lines ending with roman/arabic page refs in ToC
    if re.search(r"\.{3,}|(\.\s){3,}", stripped):
        return True
    if in_toc_block and re.search(r"\s+(?:\d{1,3}|[ivxlcdm]{1,5})$", stripped, re.IGNORECASE):
        return True
    # Page headers/footers/captions/metadata
    if re.match(r"^(?:page\s*\|\s*\d+|issn:|doi:|www\.|http|copyright\s+©)", stripped, re.IGNORECASE):
        return True
    if re.match(r"^(?:table|figure|fig\.|algorithm|equation)\s+\d+", stripped, re.IGNORECASE):
        return True
    return False


def _detect_heading_candidate(line: str, in_toc_block: bool) -> Optional[Tuple[str, int]]:
    """
    Detect authentic section/subsection headings while preserving original heading text.
    Returns (heading_title, level) or None.
    """
    if _is_noise_or_toc_line(line, in_toc_block):
        return None

    stripped = re.sub(r"\s+", " ", line.strip())
    if len(stripped) < 3 or len(stripped) > 95:
        return None
    if stripped.endswith((".", ",", ";", "?", "!")) and not re.match(r"^#{1,4}\s+", stripped):
        # Headings generally do not end with full-stop punctuation unless markdown heading
        if not re.match(r"^\d+(?:\.\d+)*\.?\s+[A-Z]", stripped):
            return None
        if len(stripped.split()) > 10:
            return None

    # Markdown headings
    md_match = re.match(r"^(#{1,4})\s+(.+)$", stripped)
    if md_match:
        title = md_match.group(2).strip()
        if len(title) >= 3 and not _is_noise_or_toc_line(title, False):
            return title, min(3, len(md_match.group(1)))

    # Dotted-decimal academic headings: e.g. "1. Introduction", "3.2 Preprocessing", "4.1.2 Setup"
    num_match = re.match(r"^(\d+(?:\.\d+){0,2}\.?)\s+([A-Z][A-Za-z0-9\s,&/\-:\(\)]{2,75})$", stripped)
    if num_match:
        sec_num_raw = num_match.group(1)
        sec_num = sec_num_raw.rstrip(".")
        sec_title_part = num_match.group(2).strip()
        # Reject plain numeric data lines / dates / page numbers ("2025 Volume", "100 Samples")
        first_num = int(sec_num.split(".")[0])
        word_count = len(sec_title_part.split())
        if first_num <= 25 and 1 <= word_count <= 10 and not re.match(r"^(?:Volume|Issue|March|April|May|June|July|August|Percent|Samples)\b", sec_title_part, re.I):
            level = min(3, sec_num.count(".") + 1)
            return f"{sec_num_raw} {sec_title_part}", level

    # Roman-numeral IEEE style headings: "I. INTRODUCTION", "III. METHODOLOGY"
    roman_match = re.match(r"^([IVXLCDM]{1,5})\.\s+([A-Z][A-Za-z0-9\s,&/\-]{2,70})$", stripped)
    if roman_match:
        return f"{roman_match.group(1)}. {roman_match.group(2).strip()}", 1

    # Known standalone unnumbered academic headings: "Abstract", "Methodology", "Conclusion", "References"
    norm_clean = re.sub(r"[:\-]+$", "", stripped).strip().lower()
    if norm_clean in _STANDALONE_HEADINGS:
        return re.sub(r"[:\-]+$", "", stripped).strip(), 1

    # Inline colon abstract heading: "Abstract: ..." or "Abstract— ..."
    inline_abs = re.match(r"^(Abstract|Keywords|Index Terms)\s*[:—\-]\s+\S+", stripped, re.IGNORECASE)
    if inline_abs:
        return inline_abs.group(1).strip().title(), 1

    return None


def build_section_hierarchy(units: List[ChunkUnit]) -> List[Dict[str, Any]]:
    """
    Identify paper sections from ordered chunks, annotate each ChunkUnit with its active
    section & role, and return a lightweight hierarchical list of section dicts.
    """
    if not units:
        return []

    raw_sections: List[Dict[str, Any]] = []
    current_section: Optional[Dict[str, Any]] = None
    in_toc_block = False

    for unit in units:
        lines = unit.content.splitlines()
        detected_in_chunk: List[Tuple[str, int, str]] = []

        for line in lines:
            low = line.strip().lower()
            if low in {"table of contents", "contents", "list of tables", "list of figures"}:
                in_toc_block = True
                continue
            if in_toc_block and re.match(r"^(?:\d+\.?\s+introduction|chapter\s+1\b|abstract\b)", low):
                # Exited ToC once narrative starts (non-leader line inside body)
                if not re.search(r"\.{3,}|\s\d+$", low):
                    in_toc_block = False

            # Leave ToC after reasonable number of ToC chunks/lines
            if in_toc_block and unit.page > 14:
                in_toc_block = False

            cand = _detect_heading_candidate(line, in_toc_block)
            if cand:
                title, level = cand
                role = normalize_section_role(title)
                detected_in_chunk.append((title, level, role))

        if detected_in_chunk:
            # Assign chunk primarily to the first newly introduced heading on this chunk
            first_title, first_level, first_role = detected_in_chunk[0]
            unit.section_title = first_title
            unit.normalized_role = first_role

            for idx_h, (title, level, role) in enumerate(detected_in_chunk):
                # Avoid duplicating exact same active heading immediately across adjacent chunks
                if current_section and current_section["title"].lower() == title.lower():
                    if unit.chunk_id is not None and unit.chunk_id not in current_section["chunk_ids"]:
                        current_section["chunk_ids"].append(unit.chunk_id)
                    current_section["page_end"] = max(current_section["page_end"], unit.page)
                    continue

                snippet_text = re.sub(r"\s+", " ", unit.content).strip()
                preview = snippet_text[:220] + ("..." if len(snippet_text) > 220 else "")
                sec_dict = {
                    "id": f"sec-{len(raw_sections) + 1}",
                    "title": title,
                    "normalized_role": role,
                    "level": level,
                    "page_start": unit.page,
                    "page_end": unit.page,
                    "chunk_ids": [unit.chunk_id] if (idx_h == 0 and unit.chunk_id is not None) else [],
                    "preview": preview,
                    "children": [],
                }
                raw_sections.append(sec_dict)
                current_section = sec_dict
        else:
            if current_section is not None:
                unit.section_title = current_section["title"]
                unit.normalized_role = current_section["normalized_role"]
                if unit.chunk_id is not None and unit.chunk_id not in current_section["chunk_ids"]:
                    current_section["chunk_ids"].append(unit.chunk_id)
                current_section["page_end"] = max(current_section["page_end"], unit.page)
            else:
                unit.section_title = "Front Matter / Overview"
                unit.normalized_role = "front_matter"

    # Build lightweight level-based nesting (level 2/3 attach under nearest preceding lower-level parent)
    root_sections: List[Dict[str, Any]] = []
    stack: List[Dict[str, Any]] = []
    for sec in raw_sections:
        lvl = sec["level"]
        while stack and stack[-1]["level"] >= lvl:
            stack.pop()
        if stack and lvl > 1:
            stack[-1]["children"].append(sec)
        else:
            root_sections.append(sec)
        stack.append(sec)

    # Cap pathological edge cases on huge theses while preserving core outline cleanly
    return root_sections[:45]

