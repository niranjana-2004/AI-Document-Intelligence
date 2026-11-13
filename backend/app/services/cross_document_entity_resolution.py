from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.embedding_services import generate_embedding

# Domain suffixes that denote equivalence vs composite / related concepts
EQUIVALENCE_SUFFIXES = {
    "language",
    "programming language",
    "protocol",
    "algorithm",
    "technique",
    "method",
    "methodology",
    "model",
    "system",
    "architecture",
    "framework",
    "dataset",
    "tool",
    "concept",
    "paradigm",
}

COMPOSITE_RELATION_SUFFIXES = {
    "flood",
    "attack",
    "exploit",
    "vulnerability",
    "handshake",
    "packet",
    "header",
    "socket",
    "connection",
    "session",
    "block",
    "table",
    "cache",
    "server",
    "client",
    "buffer",
    "overflow",
    "payload",
    "spoofing",
    "poisoning",
    "hijacking",
}

# Distinct entity pairs that must never merge (adversarial safety guards)
DISALLOWED_MERGE_PAIRS = {
    frozenset(["tcp", "udp"]),
    frozenset(["syn", "ack"]),
    frozenset(["syn", "syn flood"]),
    frozenset(["syn", "syn-ack"]),
    frozenset(["ack", "syn-ack"]),
    frozenset(["client", "server"]),
    frozenset(["encryption", "decryption"]),
    frozenset(["public key", "private key"]),
    frozenset(["precision", "recall"]),
}

# Domain keyword clusters for polysemous disambiguation
DOMAIN_CONTEXT_MARKERS = {
    "java": {
        "programming": {"programming", "language", "code", "jvm", "bytecode", "virtual machine", "compiler", "class", "object", "software", "runtime", "jdk", "jre", "source"},
        "geography": {"island", "indonesia", "jakarta", "province", "volcano", "archipelago", "sunda", "geographic", "region"},
        "coffee": {"coffee", "bean", "brew", "roast", "arabica", "robusta", "espresso", "beverage", "plantation"},
    },
    "apple": {
        "technology": {"company", "inc", "iphone", "ipad", "mac", "macbook", "ios", "macos", "tim cook", "steve jobs", "tech", "silicon"},
        "fruit": {"fruit", "tree", "orchard", "cider", "sweet", "eat", "pie", "malus", "botanical", "juice"},
    },
    "python": {
        "programming": {"programming", "language", "code", "script", "interpreter", "syntax", "library", "module", "pypi", "pip", "function", "software"},
        "reptile": {"snake", "species", "constrictor", "reptile", "burmese", "wildlife", "zoology", "habitat"},
    },
}


def normalize_concept_label(label: str) -> str:
    """Normalize concept string for comparison while preserving core meaning."""
    if not label:
        return ""
    norm = unicodedata.normalize("NFKC", label)
    # Strip parenthesized acronym or definition: e.g. "Transmission Control Protocol (TCP)" -> "Transmission Control Protocol"
    paren_match = re.search(r"\(([^)]+)\)", norm)
    if paren_match:
        norm = re.sub(r"\([^)]+\)", "", norm).strip()
    norm = norm.lower().strip()
    # Replace slashes and hyphens with spaces
    norm = re.sub(r"[-_/]+", " ", norm)
    # Remove non-alphanumeric except space
    norm = re.sub(r"[^\w\s]", "", norm)
    # Collapse multiple spaces
    norm = re.sub(r"\s+", " ", norm).strip()
    return norm


def extract_acronym_candidates(label: str) -> List[str]:
    """Generate potential acronym initials from a multi-word concept."""
    cleaned = unicodedata.normalize("NFKC", label)
    # Check parenthetical acronym directly: e.g. "Transmission Control Protocol (TCP)"
    m = re.search(r"\(([A-Z0-9]{2,8})\)", cleaned)
    candidates = []
    if m:
        candidates.append(m.group(1).upper())
    # Generate initials from words
    words = re.findall(r"[A-Za-z0-9]+", cleaned)
    if len(words) >= 2:
        initials = "".join(w[0] for w in words).upper()
        if 2 <= len(initials) <= 8:
            candidates.append(initials)
    return list(dict.fromkeys(candidates))


def is_acronym_match(term_a: str, term_b: str) -> bool:
    """Check if one term is a verified acronym expansion of the other."""
    norm_a = normalize_concept_label(term_a)
    norm_b = normalize_concept_label(term_b)
    if not norm_a or not norm_b:
        return False
    if norm_a == norm_b:
        return False

    short_term, long_term = (term_a, term_b) if len(norm_a) < len(norm_b) else (term_b, term_a)
    short_clean = re.sub(r"[^A-Za-z0-9]", "", short_term).upper()
    if not (2 <= len(short_clean) <= 8):
        return False

    acronyms = extract_acronym_candidates(long_term)
    return short_clean in acronyms


def compute_cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for a, b in zip(vec_a, vec_b):
        dot += a * b
        norm_a += a * a
        norm_b += b * b
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def check_context_disambiguation(
    concept_norm: str,
    context_a: str,
    context_b: str,
) -> Tuple[bool, str]:
    """
    Check if a polysemous word (e.g. Java, Apple, Python) has conflicting contexts.
    Returns (compatible: bool, reason: str).
    """
    if concept_norm in DOMAIN_CONTEXT_MARKERS:
        clusters = DOMAIN_CONTEXT_MARKERS[concept_norm]
        tokens_a = set(re.findall(r"\w+", context_a.lower()))
        tokens_b = set(re.findall(r"\w+", context_b.lower()))

        domain_a = None
        domain_b = None
        max_score_a = 0
        max_score_b = 0

        for d_name, d_words in clusters.items():
            overlap_a = len(tokens_a & d_words)
            overlap_b = len(tokens_b & d_words)
            if overlap_a > max_score_a:
                max_score_a = overlap_a
                domain_a = d_name
            if overlap_b > max_score_b:
                max_score_b = overlap_b
                domain_b = d_name

        if domain_a and domain_b and domain_a != domain_b and max_score_a >= 1 and max_score_b >= 1:
            return False, f"Domain mismatch for polysemous '{concept_norm}': Document A relates to '{domain_a}', Document B relates to '{domain_b}'"

    return True, "Contexts compatible"


@dataclass
class ConceptCandidate:
    document_id: int
    document_name: str
    node_key: str
    label: str
    normalized_label: str
    node_type: str
    aliases: List[str]
    description: Optional[str]
    importance_score: float
    confidence: float
    evidence: List[Dict[str, Any]]
    source_pages: List[int]
    context_excerpt: str = ""
    embedding: Optional[List[float]] = None


@dataclass
class EntityMatchDecision:
    same_entity: bool
    confidence: float
    method: str
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)


class EntityResolutionPipeline:
    """Controlled multi-signal entity resolution pipeline across document collections."""

    def __init__(self, skip_llm: bool = True):
        self.skip_llm = skip_llm
        self._embedding_cache: Dict[str, List[float]] = {}

    def get_embedding(self, text: str) -> List[float]:
        if not text:
            return []
        if text not in self._embedding_cache:
            self._embedding_cache[text] = generate_embedding(text)
        return self._embedding_cache[text]

    def evaluate_pair(
        self,
        candidate_a: ConceptCandidate,
        candidate_b: ConceptCandidate,
    ) -> EntityMatchDecision:
        """
        Evaluate whether two concept candidates from different documents refer to the same entity.
        Returns strict EntityMatchDecision.
        """
        norm_a = candidate_a.normalized_label
        norm_b = candidate_b.normalized_label

        # 0. Safety Guard: Disallowed explicit pairs
        pair_set = frozenset([norm_a, norm_b])
        if pair_set in DISALLOWED_MERGE_PAIRS:
            return EntityMatchDecision(
                same_entity=False,
                confidence=0.0,
                method="disallowed_pair_guard",
                reason=f"Terms '{candidate_a.label}' and '{candidate_b.label}' are distinct related concepts and must not be merged.",
            )

        # 1. Exact Normalized Match
        if norm_a == norm_b:
            # Check context disambiguation for polysemous words (e.g. Java)
            compat, reason = check_context_disambiguation(
                norm_a, candidate_a.context_excerpt, candidate_b.context_excerpt
            )
            if not compat:
                return EntityMatchDecision(
                    same_entity=False,
                    confidence=0.25,
                    method="context_disambiguation",
                    reason=reason,
                )
            return EntityMatchDecision(
                same_entity=True,
                confidence=0.98,
                method="exact_match",
                reason=f"Identical normalized concept label '{norm_a}' with compatible context.",
            )

        # 2. Known Aliases Check
        aliases_a = {normalize_concept_label(a) for a in candidate_a.aliases}
        aliases_b = {normalize_concept_label(b) for b in candidate_b.aliases}
        if norm_b in aliases_a or norm_a in aliases_b or (aliases_a & aliases_b):
            compat, reason = check_context_disambiguation(
                norm_a, candidate_a.context_excerpt, candidate_b.context_excerpt
            )
            if compat:
                return EntityMatchDecision(
                    same_entity=True,
                    confidence=0.95,
                    method="alias_match",
                    reason=f"Direct alias match between '{candidate_a.label}' and '{candidate_b.label}'.",
                )

        # 3. Acronym Match (e.g. TCP <-> Transmission Control Protocol, AI <-> Artificial Intelligence)
        if is_acronym_match(candidate_a.label, candidate_b.label):
            compat, reason = check_context_disambiguation(
                norm_a, candidate_a.context_excerpt, candidate_b.context_excerpt
            )
            if compat:
                return EntityMatchDecision(
                    same_entity=True,
                    confidence=0.93,
                    method="acronym_match",
                    reason=f"Verified acronym expansion between '{candidate_a.label}' and '{candidate_b.label}'.",
                )

        # 4. Equivalence Suffix Match (e.g. "Python" vs "Python programming language")
        short_cand, long_cand = (candidate_a, candidate_b) if len(norm_a) < len(norm_b) else (candidate_b, candidate_a)
        short_norm = short_cand.normalized_label
        long_norm = long_cand.normalized_label

        if long_norm.startswith(short_norm + " ") or long_norm.endswith(" " + short_norm):
            remainder = long_norm.replace(short_norm, "").strip()
            # If the remainder is an equivalence suffix (e.g. "programming language", "algorithm", "protocol")
            if remainder in EQUIVALENCE_SUFFIXES:
                compat, reason = check_context_disambiguation(
                    short_norm, candidate_a.context_excerpt, candidate_b.context_excerpt
                )
                if compat:
                    return EntityMatchDecision(
                        same_entity=True,
                        confidence=0.90,
                        method="lexical_equivalence",
                        reason=f"Concept '{long_cand.label}' is the formal expansion of '{short_cand.label}' with suffix '{remainder}'.",
                    )
            # If the remainder is a composite / related noun (e.g. "flood", "attack", "handshake"), DO NOT MERGE!
            elif any(s in remainder.split() for s in COMPOSITE_RELATION_SUFFIXES):
                return EntityMatchDecision(
                    same_entity=False,
                    confidence=0.20,
                    method="composite_suffix_guard",
                    reason=f"'{long_cand.label}' is a distinct composite concept relative to '{short_cand.label}'.",
                )

        # 5. Semantic Similarity with Context Compatibility
        emb_a = candidate_a.embedding or self.get_embedding(candidate_a.label)
        emb_b = candidate_b.embedding or self.get_embedding(candidate_b.label)
        sem_sim = compute_cosine_similarity(emb_a, emb_b)

        # High threshold required for semantic-only match
        if sem_sim >= 0.88:
            # Check context similarity as well
            if candidate_a.context_excerpt and candidate_b.context_excerpt:
                ctx_emb_a = self.get_embedding(candidate_a.context_excerpt[:200])
                ctx_emb_b = self.get_embedding(candidate_b.context_excerpt[:200])
                ctx_sim = compute_cosine_similarity(ctx_emb_a, ctx_emb_b)
                if ctx_sim < 0.40:
                    return EntityMatchDecision(
                        same_entity=False,
                        confidence=0.35,
                        method="context_incompatibility",
                        reason=f"High label similarity ({sem_sim:.2f}) but incompatible context ({ctx_sim:.2f}).",
                    )
            # Safe semantic match with compatible context
            return EntityMatchDecision(
                same_entity=True,
                confidence=round(min(0.85, sem_sim), 3),
                method="lexical_semantic_match",
                reason=f"Strong semantic label similarity ({sem_sim:.2f}) and compatible document context.",
            )

        return EntityMatchDecision(
            same_entity=False,
            confidence=round(sem_sim, 3),
            method="insufficient_similarity",
            reason=f"Similarity ({sem_sim:.2f}) below threshold for unification.",
        )


def build_candidate_index(candidates: List[ConceptCandidate]) -> Dict[str, List[int]]:
    """Build an in-memory inverted index of candidate terms to avoid O(N^2) pairwise comparisons."""
    index: Dict[str, List[int]] = {}
    for idx, c in enumerate(candidates):
        keys = set()
        # Key 1: exact normalized label
        if c.normalized_label:
            keys.add(f"norm:{c.normalized_label}")
        # Key 2: acronyms
        for acr in extract_acronym_candidates(c.label):
            keys.add(f"acr:{acr.lower()}")
        # If candidate label is itself a short acronym term (e.g. "TCP", "AI", "DEK")
        if 2 <= len(c.normalized_label) <= 8 and " " not in c.normalized_label and c.normalized_label.isalnum():
            keys.add(f"acr:{c.normalized_label.lower()}")
        # Key 3: clean tokens
        tokens = [t for t in c.normalized_label.split() if len(t) >= 3 and t not in EQUIVALENCE_SUFFIXES]
        for t in tokens:
            keys.add(f"tok:{t}")
        # Key 4: aliases
        for alias in c.aliases:
            norm_al = normalize_concept_label(alias)
            if norm_al:
                keys.add(f"alias:{norm_al}")

        for k in keys:
            index.setdefault(k, []).append(idx)

    return index

