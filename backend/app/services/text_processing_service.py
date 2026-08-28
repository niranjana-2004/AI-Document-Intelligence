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

def detect_chunk_category(text: str) -> str | None:
    """
    Detect the category/section represented by a document chunk.
    """

    text_lower = text.lower()

    category_markers = {
        "education": [
            "educational qualifications",
            "higher secondary education",
            "secondary school education",
        ],

        "projects": [
            "projects done",
            "title:",
            "aim:",
            "technical functionalities:",
        ],

        "internship": [
            "internships done",
            "organization name:",
            "data science intern",
            "responsibilities:",
        ],

        "workshops": [
            "workshops done",
            "bootcamp",
            "drone workshop",
        ],

        "certifications": [
            "certifications done",
            "introduction to deep learning",
            "introduction to artificial intelligence",
            "data analytics job simulation",
        ],

        "awards": [
            "awards and achievements",
            "event volunteer",
            "event coordinator",
        ]
    }

    for category, markers in category_markers.items():

        for marker in markers:

            if marker in text_lower:
                return category

    return None
    
def chunk_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 200
) -> list[str]:
    """
    Split text into overlapping chunks.

    chunk_size:
        Maximum number of characters in each chunk.

    overlap:
        Number of characters shared between consecutive chunks.
    """

    if not text:
        return []

    if overlap >= chunk_size:
        raise ValueError(
            "overlap must be smaller than chunk_size"
        )

    chunks = []

    start = 0
    text_length = len(text)

    while start < text_length:

        end = start + chunk_size

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks