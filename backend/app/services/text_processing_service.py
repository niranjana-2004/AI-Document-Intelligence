import re


def clean_text(text: str) -> str:
    """
    Clean and normalize extracted document text.
    """

    if not text:
        return ""

    # Normalize line endings
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Remove excessive spaces and tabs
    text = re.sub(r"[ \t]+", " ", text)

    # Remove excessive blank lines
    text = re.sub(r"\n\s*\n+", "\n\n", text)

    # Remove spaces at the beginning/end of lines
    text = "\n".join(
        line.strip()
        for line in text.splitlines()
    )

    return text.strip()


# --------------------------------------------------
# SECTION DETECTION
# --------------------------------------------------

SECTION_MARKERS = {
    "career_aspiration": [
        "career aspiration",
    ],

    "education": [
        "educational qualifications",
    ],

    "projects": [
        "projects done",
    ],

    "internship": [
        "internships done",
    ],

    "workshops": [
        "workshops done",
    ],

    "technical_skills": [
        "technical skills",
    ],

    "awards": [
        "awards and achievements",
    ],

    "extracurricular": [
        "extra curricular activities",
        "extracurricular activities",
    ],

    "interpersonal_skills": [
        "interpersonal skills",
    ],

    "languages": [
        "languages known",
    ],

    "personal_details": [
        "personal details",
    ],

    "certifications": [
        "certifications done",
    ],
}


def detect_section(line: str) -> str | None:
    """
    Detect whether a line represents a document section heading.

    Returns the normalized section name or None.
    """

    line_lower = line.strip().lower()

    for section, markers in SECTION_MARKERS.items():

        for marker in markers:

            if line_lower == marker:
                return section

    return None


def detect_chunk_category(text: str) -> str | None:
    """
    Detect the category/section represented by a document chunk.
    """

    lines = text.splitlines()

    for line in lines:

        section = detect_section(line)

        if section:
            return section

    return None


# --------------------------------------------------
# SECTION-AWARE CHUNKING
# --------------------------------------------------

def split_large_section(
    section_text: str,
    chunk_size: int,
    overlap: int
) -> list[str]:
    """
    Split a large section into smaller overlapping chunks.

    This is only used when a section is larger than chunk_size.
    """

    if not section_text:
        return []

    if overlap >= chunk_size:
        raise ValueError(
            "overlap must be smaller than chunk_size"
        )

    chunks = []

    start = 0
    text_length = len(section_text)

    while start < text_length:

        end = start + chunk_size

        chunk = section_text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 200
) -> list[str]:
    """
    Split document text into section-aware chunks.

    Document sections are kept together whenever possible.

    If a section exceeds chunk_size, only that section is split
    into smaller overlapping chunks.

    This prevents unrelated sections such as:
        Technical Skills
        Awards
        Certifications
        Workshops

    from being unnecessarily placed in the same chunk.
    """

    if not text:
        return []

    if overlap >= chunk_size:
        raise ValueError(
            "overlap must be smaller than chunk_size"
        )

    lines = text.splitlines()

    sections = []

    current_section = "general"
    current_lines = []

    for line in lines:

        detected_section = detect_section(line)

        if detected_section:

            # Save previous section
            if current_lines:

                sections.append(
                    (
                        current_section,
                        "\n".join(current_lines).strip()
                    )
                )

            current_section = detected_section

            current_lines = [line]

        else:
            current_lines.append(line)

    # Save final section
    if current_lines:

        sections.append(
            (
                current_section,
                "\n".join(current_lines).strip()
            )
        )

    chunks = []

    for section_name, section_text in sections:

        if not section_text:
            continue

        # Keep small sections intact
        if len(section_text) <= chunk_size:

            chunks.append(section_text)

        else:

            # Split only large sections
            section_chunks = split_large_section(
                section_text,
                chunk_size,
                overlap
            )

            chunks.extend(section_chunks)

    return chunks


_EXCERPT_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "by", "can", "could",
    "did", "do", "does", "for", "from", "had", "has", "have", "how", "i",
    "in", "is", "it", "its", "me", "of", "on", "or", "that", "the", "their",
    "them", "there", "these", "they", "this", "to", "was", "we", "were",
    "what", "when", "where", "which", "who", "why", "will", "with", "would",
    "you", "your"
}


def extract_relevant_excerpt(
    text: str,
    query: str = "",
    max_chars: int = 240
) -> str:
    """
    Deterministically select a concise, readable supporting excerpt from a chunk
    by scoring sentences or sliding text windows against meaningful query terms.
    Preserves original wording without relying on LLM generation.
    """
    if not text:
        return ""

    # Strip redundant OCR page banner headers if present and collapse extra newlines
    cleaned = re.sub(r"---\s*Page\s+\d+\s*---\s*", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if not cleaned:
        return ""

    if len(cleaned) <= max_chars:
        return cleaned

    query_tokens = [
        t for t in re.findall(r"[a-zA-Z0-9]{2,}", (query or "").lower())
        if t not in _EXCERPT_STOPWORDS
    ]
    unique_tokens = list(dict.fromkeys(query_tokens))
    query_phrase = " ".join(unique_tokens[:4])

    # Split into sentence-like segments first
    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+", cleaned)
        if s.strip()
    ]

    def score_segment(seg: str) -> float:
        seg_lower = seg.lower()
        seg_words = set(re.findall(r"[a-zA-Z0-9]{2,}", seg_lower))
        if not unique_tokens:
            return 0.0
        unique_hits = sum(1 for tok in unique_tokens if tok in seg_words)
        partial_hits = sum(
            1 for tok in unique_tokens
            if tok not in seg_words and tok in seg_lower
        )
        phrase_bonus = 3.0 if (len(unique_tokens) >= 2 and query_phrase in seg_lower) else 0.0
        return unique_hits * 3.0 + partial_hits * 1.0 + phrase_bonus

    best_idx = 0
    best_score = -1.0

    if len(sentences) > 1 and unique_tokens:
        for idx, sent in enumerate(sentences):
            window = sent
            if idx + 1 < len(sentences) and len(sent) + len(sentences[idx + 1]) + 1 <= max_chars:
                window = f"{sent} {sentences[idx + 1]}"
            sc = score_segment(window)
            if sc > best_score:
                best_score = sc
                best_idx = idx

        # Assemble 1-2 sentences around best_idx within max_chars
        selected = sentences[best_idx]
        if best_idx + 1 < len(sentences):
            combined = f"{selected} {sentences[best_idx + 1]}"
            if len(combined) <= max_chars:
                selected = combined
        prefix = "... " if best_idx > 0 else ""
        if len(selected) <= max_chars:
            suffix = " ..." if len(cleaned) > len(selected) and not selected.endswith((".", "!", "?")) else ""
            result = f"{prefix}{selected}{suffix}".strip()
            if len(result) <= max_chars + 8:
                return result
    else:
        selected = cleaned

    # Single long sentence/OCR block: center window on highest-density query match
    anchor = 0
    if unique_tokens:
        words_iter = list(re.finditer(r"[a-zA-Z0-9]{2,}", cleaned.lower()))
        best_pos_score = -1.0
        token_set = set(unique_tokens)
        for m in words_iter:
            pos = m.start()
            window_end = min(len(cleaned), pos + max_chars)
            sub_lower = cleaned[max(0, pos - 40):window_end].lower()
            sub_words = set(re.findall(r"[a-zA-Z0-9]{2,}", sub_lower))
            sc = float(len(token_set & sub_words))
            if sc > best_pos_score:
                best_pos_score = sc
                anchor = max(0, pos - 45)

    # Align window start and end to word boundaries
    if anchor > 0:
        space_after = cleaned.find(" ", anchor)
        if 0 < space_after < anchor + 25:
            anchor = space_after + 1

    slice_end = min(len(cleaned), anchor + max_chars)
    snippet = cleaned[anchor:slice_end]
    if slice_end < len(cleaned):
        last_space = snippet.rfind(" ")
        if last_space > max_chars // 2:
            snippet = snippet[:last_space]
        snippet = snippet.rstrip(" ,;:-") + "..."
    if anchor > 0:
        snippet = "..." + snippet.lstrip(" ,;:-")

    return snippet.strip()