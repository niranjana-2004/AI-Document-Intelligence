"""
Candidate Ranker Service for Cognidocs OCR 3.5.
Provides explainable candidate representation (WordCandidate) and multi-signal
ranking with an evidence-grounded Safety Gate.
Enforces the hierarchy of trust:
1. Handwritten image evidence
2. OCR model evidence
3. Character/word visual evidence
4. Document-local repetition
5. Local context
6. Technical vocabulary
7. Language plausibility
"""

import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Tuple, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class WordCandidate:
    word_id: str
    page_number: int
    line_id: int
    word_index: int
    original_text: str
    candidate_text: str
    bounding_box: List[int]
    confidence: float = 0.0
    character_confidence: float = 0.0
    visual_similarity: float = 0.0
    boundary_confidence: float = 0.0
    context_score: float = 0.0
    language_score: float = 0.0
    technical_score: float = 0.0
    document_score: float = 0.0
    final_score: float = 0.0
    evidence: List[str] = field(default_factory=list)
    decision: str = "RAW"  # RAW, SUGGESTED, ACCEPTED, REJECTED, MANUAL
    source: str = "ORIGINAL"  # ORIGINAL, BOUNDARY_SPLIT, BOUNDARY_MERGE, CHAR_AMBIGUITY, LOCAL_CONTEXT, DOCUMENT_CONSENSUS, PHRASE, TECHNICAL

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def score_candidate(
    candidate: WordCandidate,
    is_boundary_op: bool = False,
    is_common_protected: bool = False
) -> WordCandidate:
    """
    Calculate an explainable weighted composite score and assign an auditable decision state.
    
    Weights:
    - Visual similarity: 0.25 (Optical cursive stroke agreement)
    - Boundary confidence: 0.20 (Physical whitespace dip or gap metric)
    - Context score: 0.20 (Local n-gram colocation agreement)
    - Language score: 0.15 (Lexical plausibility in academic English lexicon)
    - Technical score: 0.10 (Subject domain dictionary presence)
    - Document score: 0.10 (Document-local repetition consensus)
    """
    v = candidate.visual_similarity
    b = candidate.boundary_confidence
    c = candidate.context_score
    l = candidate.language_score
    t = candidate.technical_score
    d = candidate.document_score

    if is_boundary_op:
        # Boundary operations (splits/merges) rely heavily on physical spacing
        composite = (
            b * 0.35 +
            l * 0.25 +
            c * 0.20 +
            v * 0.10 +
            t * 0.05 +
            d * 0.05
        )
    else:
        # Character substitutions require strong visual stroke agreement
        composite = (
            v * 0.30 +
            c * 0.20 +
            l * 0.20 +
            d * 0.10 +
            t * 0.10 +
            b * 0.10
        )

    composite = min(0.99, max(0.0, composite))
    candidate.final_score = round(composite, 3)

    # Count distinct positive corroborations (score >= 0.70)
    corroborating_signals = 0
    if v >= 0.65:
        corroborating_signals += 1
    if b >= 0.65:
        corroborating_signals += 1
    if c >= 0.70:
        corroborating_signals += 1
    if l >= 0.80:
        corroborating_signals += 1
    if t >= 0.70:
        corroborating_signals += 1
    if d >= 0.70:
        corroborating_signals += 1

    # Safety Gate Logic:
    # 1. Protection for valid high-confidence words against arbitrary mutation
    if is_common_protected and not is_boundary_op:
        if candidate.final_score < 0.85 or corroborating_signals < 3:
            candidate.decision = "RAW"
            return candidate

    # 2. Strict visual grounding: non-boundary candidates with visual similarity < 0.55 are rejected
    if not is_boundary_op and v < 0.55:
        candidate.decision = "REJECTED"
        return candidate

    # 3. Decision assignment
    if candidate.final_score >= 0.78 and corroborating_signals >= 2:
        candidate.decision = "ACCEPTED"
    elif candidate.final_score >= 0.58:
        candidate.decision = "SUGGESTED"
    else:
        candidate.decision = "REJECTED"

    return candidate


def rank_candidates_for_token(
    candidates: List[WordCandidate],
    is_common_protected: bool = False
) -> Tuple[WordCandidate, List[WordCandidate]]:
    """
    Score and rank a set of candidates for a single token position.
    Always includes the original OCR as a baseline option.
    Returns (winning_candidate, ranked_candidates_list).
    """
    if not candidates:
        raise ValueError("Candidate list cannot be empty.")

    scored = []
    for c in candidates:
        is_boundary = (c.source in ["BOUNDARY_SPLIT", "BOUNDARY_MERGE"])
        scored_c = score_candidate(c, is_boundary_op=is_boundary, is_common_protected=is_common_protected)
        scored.append(scored_c)

    # Sort descending by final_score, breaking ties with visual_similarity
    scored.sort(key=lambda x: (x.final_score, x.visual_similarity), reverse=True)

    winner = scored[0]

    # Conservative rule: If the top non-original candidate is only SUGGESTED or REJECTED,
    # and the original is valid, keep original as the active text while keeping suggestion in metadata.
    orig_cand = next((c for c in scored if c.source == "ORIGINAL"), scored[-1])

    if winner.source != "ORIGINAL" and winner.decision != "ACCEPTED":
        # Winner is suggested but not auto-accepted: active text remains original
        return orig_cand, scored

    return winner, scored

