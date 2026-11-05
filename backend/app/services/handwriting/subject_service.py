import logging
import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.document import Document
from app.services.handwriting.handwritten_source_service import get_document_transcription_source
from app.services.handwriting.ollama_client import query_ollama

logger = logging.getLogger(__name__)

ACADEMIC_SUBJECTS = [
    "Computer Science & Networking",
    "Artificial Intelligence & Data Science",
    "Mathematics & Statistics",
    "Physics & Engineering",
    "Chemistry & Materials",
    "Biology & Life Sciences",
    "Economics & Business",
    "Humanities & General"
]

# Fast heuristic keywords for rapid, deterministic classification
SUBJECT_KEYWORD_RULES = [
    (
        "Computer Science & Networking",
        [
            r'\b(?:tcp|udp|ip|syn|ack|rst|tcb|handshake|packet|router|socket|subnet|firewall|dns|http|https|ethernet|dos|ddos)\b',
            r'\b(?:css|html|javascript|python|java|c\+\+|sql|database|api|endpoint|frontend|backend|recursion|compiler)\b'
        ]
    ),
    (
        "Artificial Intelligence & Data Science",
        [
            r'\b(?:machine\s+learning|deep\s+learning|neural\s+network|gradient\s+descent|backpropagation|transformer|attention)\b',
            r'\b(?:dataset|dataframe|clustering|pca|regression|classification|supervised|unsupervised|nlp|embedding)\b'
        ]
    ),
    (
        "Mathematics & Statistics",
        [
            r'\b(?:derivative|integral|differential|matrix|eigenvalue|eigenvector|determinant|calculus|polynomial|algebra)\b',
            r'\b(?:variance|standard\s+deviation|probability|hypothesis|distribution|normal\s+distribution|theorem|proof)\b'
        ]
    ),
    (
        "Physics & Engineering",
        [
            r'\b(?:velocity|acceleration|momentum|kinetic|potential|thermodynamics|entropy|quantum|electromagnetism)\b',
            r'\b(?:resistor|capacitor|inductor|voltage|current|circuit|ohm|kirchhoff|torque|gravity|optics)\b'
        ]
    ),
    (
        "Chemistry & Materials",
        [
            r'\b(?:molecule|covalent|ionic|acid|base|ph|equilibrium|stoichiometry|titration|polymer|catalyst)\b',
            r'\b(?:organic\s+chemistry|alkane|alkene|benzene|enthalpy|periodic\s+table|molar|electronegativity)\b'
        ]
    ),
    (
        "Biology & Life Sciences",
        [
            r'\b(?:cell|mitosis|meiosis|dna|rna|ribosome|mitochondria|photosynthesis|enzyme|protein|chromosome)\b',
            r'\b(?:organism|evolution|genetics|mutation|ecosystem|homeostasis|metabolism|bacteria|virus)\b'
        ]
    ),
    (
        "Economics & Business",
        [
            r'\b(?:inflation|gdp|monetary|fiscal|elasticity|macroeconomics|microeconomics|interest\s+rate|liquidity)\b',
            r'\b(?:balance\s+sheet|asset|liability|equity|revenue|profit|margin|dividend|portfolio|depreciation)\b'
        ]
    )
]


def classify_subject_from_text(text: str) -> str:
    """
    Classify transcribed document text into an academic discipline.
    Uses regex keyword matching with fast local Ollama LLM fallback for ambiguous text.
    """
    if not text or len(text.strip()) < 10:
        return "Humanities & General"

    text_lower = text.lower()

    # 1. Evaluate keyword rules
    scores: Dict[str, int] = {}
    for subject, pattern_list in SUBJECT_KEYWORD_RULES:
        match_count = 0
        for pattern in pattern_list:
            matches = re.findall(pattern, text_lower)
            match_count += len(matches)
        scores[subject] = match_count

    best_subject = max(scores, key=scores.get)
    if scores[best_subject] >= 3:
        logger.info(f"Heuristically classified subject as '{best_subject}' (matches: {scores[best_subject]})")
        return best_subject

    # 2. Local LLM Classification Fallback via Ollama
    try:
        sample_text = text[:1500]
        subjects_list = "\n".join(f"- {s}" for s in ACADEMIC_SUBJECTS)
        prompt = (
            f"You are an academic classifier. Below is an excerpt of student handwritten lecture notes:\n\n"
            f'"""\n{sample_text}\n"""\n\n'
            f"Select exactly ONE academic discipline from this list that best categorizes these notes:\n"
            f"{subjects_list}\n\n"
            f"OUTPUT ONLY THE EXACT SUBJECT NAME FROM THE LIST, NOTHING ELSE:"
        )

        resp = query_ollama(prompt, temperature=0.0).strip()
        for subject in ACADEMIC_SUBJECTS:
            if subject.lower() in resp.lower():
                logger.info(f"LLM classified subject as '{subject}'")
                return subject
    except Exception as error:
        logger.warning(f"LLM subject classification error: {error}. Using heuristic: '{best_subject}'")

    return best_subject if scores[best_subject] > 0 else "Humanities & General"


def auto_detect_and_set_subject(document_id: int, user_id: int, db: Session) -> str:
    """
    Detect the subject of a handwritten document from its transcribed text and persist it.
    """
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user_id).first()
    if not doc:
        raise ValueError("Document not found")

    source_data = get_document_transcription_source(document_id, db, user_id=user_id)
    text = source_data.get("full_text", "")
    detected_subject = classify_subject_from_text(text)

    doc.subject = detected_subject
    db.commit()
    db.refresh(doc)
    logger.info(f"Updated document #{document_id} subject to '{detected_subject}'")
    return detected_subject


def set_document_subject(document_id: int, user_id: int, subject: str, db: Session) -> str:
    """
    Manually override and persist a document's academic subject.
    """
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user_id).first()
    if not doc:
        raise ValueError("Document not found")

    # Validate against known subjects or allow custom academic label
    subject_cleaned = subject.strip()
    if not subject_cleaned:
        subject_cleaned = "Humanities & General"

    doc.subject = subject_cleaned
    db.commit()
    db.refresh(doc)
    logger.info(f"Manually set document #{document_id} subject to '{subject_cleaned}'")
    return subject_cleaned

