import logging
import re
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Known academic section heading patterns
SECTION_KEYWORDS = [
    r'^(?:1\.|2\.|3\.|4\.|5\.|6\.|7\.|8\.|9\.|10\.)\s+[A-Za-z]',
    r'^(?:[I|V|X]+\.)\s+[A-Za-z]',
    r'^(?:how\s+the\s+attack\s+works|how\s+it\s+works|mechanism|working):?',
    r'^(?:impact|consequences|effects|implications):?',
    r'^(?:mitigation|countermeasures|defenses?|prevention|remedy):?',
    r'^(?:definition|overview|introduction|concept|background):?',
    r'^(?:summary|takeaways|conclusion|key\s+points):?',
    r'^(?:advantages?|disadvantages?|pros?|cons?):?',
    r'^(?:example|use\s+case|scenario|problem):?',
    r'^(?:formula|equation|theorem|proof):?'
]

MATH_PATTERNS = [
    r'[\=≠≤≥≈±∑∫√∂]',
    r'\b(?:lim|sin|cos|tan|log|ln|exp)\b',
    r'\b[a-zA-Z]\s*=\s*[0-9a-zA-Z]',
    r'[\^_{}\\]'
]


def classify_line_semantics(
    text: str,
    line_idx: int,
    total_lines: int,
    bbox: List[int],
    page_w: int,
    page_h: int
) -> str:
    """
    Classify an individual recognized text line into a structural semantic type:
    - 'title'
    - 'heading'
    - 'list_item'
    - 'math'
    - 'paragraph'
    """
    cleaned = text.strip()
    if not cleaned:
        return "empty"

    bx, by, bw, bh = bbox if len(bbox) == 4 else (0, 0, page_w, 50)
    rel_y = by / max(1, page_h)

    # 1. Title detection: top 18% of page, prominent text or matches title keywords
    is_top_region = rel_y < 0.18
    is_title_phrase = bool(re.search(r'\b(?:notes\s+on|chapter\s+\d|lecture\s+\d|introduction\s+to)\b', cleaned, re.IGNORECASE))
    if (is_top_region and is_title_phrase) or (line_idx <= 2 and is_title_phrase):
        return "title"

    # 2. Section Heading detection
    # Numbered heading pattern within the first 35 chars (e.g., "1. TCP SYN Flood", "TCP Attacks 1. TCP SYN Flood")
    if len(cleaned) <= 65 and re.search(r'(?:^|\b)(?:[0-9]{1,2}\.|[I|V|X]+\.)\s+[A-Za-z]', cleaned[:35]):
        return "heading"

    for pattern in SECTION_KEYWORDS:
        if re.search(pattern, cleaned, re.IGNORECASE):
            return "heading"

    # Ending with a colon often indicates a heading / label
    if cleaned.endswith(":") and len(cleaned.split()) <= 6:
        return "heading"

    # 3. List Item detection (bullet or numbered list)
    if re.match(r'^(?:[-*•+]|\d+\.|\([a-zA-Z0-9]+\))\s+', cleaned):
        return "list_item"

    # Indented relative to left margin by > 6% of page width
    rel_x = bx / max(1, page_w)
    if rel_x > 0.08 and re.match(r'^(?:[-*•+]|\w+\s*:)', cleaned):
        return "list_item"

    # 4. Mathematical equation detection
    math_match_count = sum(1 for p in MATH_PATTERNS if re.search(p, cleaned))
    if math_match_count >= 2:
        return "math"

    # 5. Default to body paragraph
    return "paragraph"


def analyze_document_structure(
    lines: List[Dict[str, Any]],
    page_width: int = 1800,
    page_height: int = 2400
) -> Dict[str, Any]:
    """
    Analyze OCR line outputs and synthesize a structured, hierarchical document layout.

    Transforms flat line sequences into cohesive semantic blocks:
    - Titles
    - Headings
    - Multi-line Paragraphs (with sentence flow preserved)
    - Lists (with structured items)
    - Mathematical blocks

    Returns:
        {
            "blocks": [
                {
                    "id": str,
                    "type": "title" | "heading" | "paragraph" | "list" | "math",
                    "text": str,
                    "confidence": float,
                    "bbox": [x, y, w, h],
                    "items": [...]  # only for type == 'list'
                }, ...
            ],
            "total_blocks": int,
            "has_headings": bool,
            "has_lists": bool,
            "has_math": bool
        }
    """
    if not lines:
        return {
            "blocks": [],
            "total_blocks": 0,
            "has_headings": False,
            "has_lists": False,
            "has_math": False
        }

    total_lines = len(lines)
    classified_lines = []

    for idx, line in enumerate(lines):
        text = line.get("text", "").strip()
        if not text:
            continue
        bbox = line.get("bbox", [0, 0, page_width, 40])
        conf = line.get("confidence", 80.0)
        sem_type = classify_line_semantics(text, idx + 1, total_lines, bbox, page_width, page_height)
        classified_lines.append({
            "line_idx": idx + 1,
            "text": text,
            "bbox": bbox,
            "confidence": conf,
            "sem_type": sem_type
        })

    # Group into blocks
    blocks = []
    current_block: Optional[Dict[str, Any]] = None

    def _flush_block():
        nonlocal current_block
        if current_block is not None:
            # Calculate composite bounding box and average confidence
            confs = current_block.pop("_confs", [80.0])
            current_block["confidence"] = round(sum(confs) / len(confs), 1) if confs else 80.0
            blocks.append(current_block)
            current_block = None

    block_id_counter = 1

    for item in classified_lines:
        stype = item["sem_type"]
        text = item["text"]
        bbox = item["bbox"]
        conf = item["confidence"]

        if stype in ("title", "heading"):
            _flush_block()
            blocks.append({
                "id": f"blk_{block_id_counter}",
                "type": stype,
                "text": text,
                "confidence": conf,
                "bbox": bbox
            })
            block_id_counter += 1

        elif stype == "list_item":
            clean_item_text = re.sub(r'^(?:[-*•+]|\d+\.|\([a-zA-Z0-9]+\))\s*', '', text)
            if current_block is not None and current_block["type"] == "list":
                # Append to existing list block
                current_block["items"].append(clean_item_text)
                current_block["_confs"].append(conf)
                # Expand bounding box
                bx1 = min(current_block["bbox"][0], bbox[0])
                by1 = min(current_block["bbox"][1], bbox[1])
                bx2 = max(current_block["bbox"][0] + current_block["bbox"][2], bbox[0] + bbox[2])
                by2 = max(current_block["bbox"][1] + current_block["bbox"][3], bbox[1] + bbox[3])
                current_block["bbox"] = [bx1, by1, bx2 - bx1, by2 - by1]
            else:
                _flush_block()
                current_block = {
                    "id": f"blk_{block_id_counter}",
                    "type": "list",
                    "text": "- " + clean_item_text,
                    "items": [clean_item_text],
                    "bbox": list(bbox),
                    "_confs": [conf]
                }
                block_id_counter += 1

        elif stype == "math":
            _flush_block()
            blocks.append({
                "id": f"blk_{block_id_counter}",
                "type": "math",
                "text": text,
                "confidence": conf,
                "bbox": bbox
            })
            block_id_counter += 1

        else:  # paragraph
            if current_block is not None and current_block["type"] == "paragraph":
                # Append line to paragraph with natural spacing
                current_block["text"] += " " + text
                current_block["_confs"].append(conf)
                bx1 = min(current_block["bbox"][0], bbox[0])
                by1 = min(current_block["bbox"][1], bbox[1])
                bx2 = max(current_block["bbox"][0] + current_block["bbox"][2], bbox[0] + bbox[2])
                by2 = max(current_block["bbox"][1] + current_block["bbox"][3], bbox[1] + bbox[3])
                current_block["bbox"] = [bx1, by1, bx2 - bx1, by2 - by1]
            else:
                _flush_block()
                current_block = {
                    "id": f"blk_{block_id_counter}",
                    "type": "paragraph",
                    "text": text,
                    "bbox": list(bbox),
                    "_confs": [conf]
                }
                block_id_counter += 1

    _flush_block()

    has_headings = any(b["type"] == "heading" for b in blocks)
    has_lists = any(b["type"] == "list" for b in blocks)
    has_math = any(b["type"] == "math" for b in blocks)

    return {
        "blocks": blocks,
        "total_blocks": len(blocks),
        "has_headings": has_headings,
        "has_lists": has_lists,
        "has_math": has_math
    }


def reconstruct_structured_markdown(blocks: List[Dict[str, Any]]) -> str:
    """
    Reconstruct a clean, semantically formatted Markdown document from structured blocks.
    Separates paragraphs with double newlines (\n\n) to ensure accurate semantic chunking.
    """
    md_parts = []
    for block in blocks:
        btype = block.get("type", "paragraph")
        text = block.get("text", "").strip()
        if not text:
            continue

        if btype == "title":
            md_parts.append(f"# {text}")
        elif btype == "heading":
            md_parts.append(f"## {text}")
        elif btype == "list":
            items = block.get("items", [])
            if items:
                md_parts.append("\n".join(f"- {item}" for item in items))
            else:
                md_parts.append(text)
        elif btype == "math":
            md_parts.append(f"$$\n{text}\n$$")
        else:  # paragraph
            md_parts.append(text)

    return "\n\n".join(md_parts).strip()
