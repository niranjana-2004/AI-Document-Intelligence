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