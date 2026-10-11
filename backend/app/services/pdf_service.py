from pathlib import Path

from pypdf import PdfReader


def extract_pages_from_pdf(file_path: Path) -> list[dict]:
    """
    Extract text from each page of a PDF with its 1-based page number.

    Returns:
        list[dict]: A list of dicts, each with:
            - "page": int (1-based page number)
            - "text": str (extracted text for that page)
    """
    reader = PdfReader(file_path)
    pages = []

    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append({
            "page": page_num,
            "text": text
        })

    return pages


def extract_text_from_pdf(file_path: Path) -> str:
    """
    Extract text from all pages of a PDF as a single string.
    Preserves backward compatibility for callers expecting a single string.
    """
    pages = extract_pages_from_pdf(file_path)
    extracted_text = [
        p["text"]
        for p in pages
        if p["text"].strip()
    ]

    return "\n".join(extracted_text)