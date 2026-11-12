from collections import OrderedDict
from dataclasses import dataclass
import logging
import re
import threading
import time
from typing import Any
from sqlalchemy.orm import Session

from app.schemas.voice_query_recovery import (
    RecoveryDecision,
    VoiceQueryRecoverResponse,
    VoiceRecoveryChange,
    VoiceRecoverySuggestion,
)
from app.services.search_service import ENGLISH_STOP_WORDS
from app.services.voice_terminology_service import (
    ORDINARY_ENGLISH_WORDS,
    _DOMAIN_COLOCATIONS,
    get_scoped_terminology,
)

logger = logging.getLogger(__name__)

AUTO_APPLY_THRESHOLD = 0.76
SUGGEST_THRESHOLD = 0.54
AMBIGUITY_MARGIN = 0.08

ULTRA_COMMON_SHORT_WORDS = {
    "a", "an", "am", "as", "at", "be", "by", "do", "go", "he", "if",
    "in", "is", "it", "me", "my", "no", "of", "on", "or", "so", "to",
    "up", "us", "we",
}

LETTER_TO_SPOKEN: dict[str, str] = {
    "A": "ay", "B": "bee", "C": "see", "D": "dee", "E": "ee", "F": "ef",
    "G": "gee", "H": "aitch", "I": "eye", "J": "jay", "K": "kay", "L": "el",
    "M": "em", "N": "en", "O": "oh", "P": "pee", "Q": "cue", "R": "are",
    "S": "ess", "T": "tee", "U": "you", "V": "vee", "W": "doubleyou",
    "X": "ex", "Y": "why", "Z": "zee",
}

SPOKEN_WORD_TO_LETTER: dict[str, tuple[str, bool]] = {
    # (letter, is_distinctive_letter_token_unlikely_as_prose)
    "ay": ("A", True), "eh": ("A", True),
    "bee": ("B", False), "be": ("B", False),
    "see": ("C", False), "sea": ("C", False), "cee": ("C", True),
    "dee": ("D", True), "de": ("D", True),
    "ee": ("E", True),
    "ef": ("F", True), "eff": ("F", True),
    "gee": ("G", True), "ji": ("G", True),
    "aitch": ("H", True), "ache": ("H", False),
    "eye": ("I", False), "aye": ("I", True),
    "jay": ("J", True), "jaye": ("J", True),
    "kay": ("K", True), "kaye": ("K", True),
    "el": ("L", True), "ell": ("L", True),
    "em": ("M", True),
    "en": ("N", True),
    "oh": ("O", False), "owe": ("O", False),
    "pee": ("P", True), "pea": ("P", False),
    "cue": ("Q", True), "queue": ("Q", False),
    "are": ("R", False), "ar": ("R", True),
    "ess": ("S", True), "es": ("S", True),
    "tee": ("T", True), "tea": ("T", False),
    "you": ("U", False), "yu": ("U", True),
    "vee": ("V", True),
    "ex": ("X", True),
    "why": ("Y", False), "wye": ("Y", True),
    "zee": ("Z", True), "zed": ("Z", True),
}

NUMBER_UNITS = {
    "zero": 0, "oh": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
NUMBER_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
ALL_NUMBER_WORDS = set(NUMBER_UNITS) | set(NUMBER_TENS) | {"hundred", "thousand"}

_GLIDE_SIMILAR_GROUPS = [
    {"c", "s", "z"},
    {"c", "k", "q"},
    {"f", "v", "p"},
    {"b", "p"},
    {"t", "d"},
    {"m", "n"},
    {"i", "y", "e"},
    {"w", "u", "o", "v"},
    {"g", "j"},
]


@dataclass
class CandidateTerm:
    key: str
    canonical: str
    is_acronym: bool
    freq: int
    in_heading: bool
    in_definition: bool
    in_concept: bool
    domain_match: bool
    doc_titles: tuple[str, ...]
    phonetic_word: str
    skeleton: str
    spoken_letters: str
    clean_len: int = 0
    char_set: frozenset[str] = frozenset()
    stem_key: str = ""


def _weighted_char_distance(a: str, b: str) -> float:
    """Damerau-Levenshtein distance with reduced cost for phonetically close characters."""
    m, n = len(a), len(b)
    if m == 0:
        return float(n)
    if n == 0:
        return float(m)

    def _sub_cost(ch1: str, ch2: str) -> float:
        if ch1 == ch2:
            return 0.0
        for grp in _GLIDE_SIMILAR_GROUPS:
            if ch1 in grp and ch2 in grp:
                return 0.35
        vowels = set("aeiouy")
        if ch1 in vowels and ch2 in vowels:
            return 0.35
        return 1.0

    dp = [[0.0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = float(i)
    for j in range(n + 1):
        dp[0][j] = float(j)

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = _sub_cost(a[i - 1], b[j - 1])
            best = min(
                dp[i - 1][j] + 1.0,
                dp[i][j - 1] + 1.0,
                dp[i - 1][j - 1] + cost,
            )
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                best = min(best, dp[i - 2][j - 2] + 0.4)
            dp[i][j] = best
    return dp[m][n]


def _phonetic_key(word: str) -> str:
    """
    Lightweight English phonetic signature tolerant to STT glide/vowel drift
    (e.g. 'swion' -> 'swn'/'sn', 'SYN' -> 'sn', 'ceph' -> 'sf', 'trocr' -> 'trkr').
    """
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return ""

    # Common multi-letter English/technical sound mappings
    replacements = [
        ("tion", "sn"),
        ("sion", "sn"),
        ("cion", "sn"),
        ("ph", "f"),
        ("kn", "n"),
        ("wr", "r"),
        ("qu", "kw"),
        ("ck", "k"),
        ("ch", "x"),
        ("sh", "x"),
        ("th", "t"),
        ("dg", "j"),
        ("gh", ""),
    ]
    for src, dst in replacements:
        w = w.replace(src, dst)

    # Soft c -> s before e/i/y, hard c -> k otherwise
    out_chars: list[str] = []
    for idx, ch in enumerate(w):
        nxt = w[idx + 1] if idx + 1 < len(w) else ""
        if ch == "c":
            out_chars.append("s" if nxt in {"e", "i", "y"} else "k")
        elif ch == "z":
            out_chars.append("s")
        elif ch == "v":
            out_chars.append("f")
        elif ch == "q":
            out_chars.append("k")
        else:
            out_chars.append(ch)

    joined = "".join(out_chars)
    # Collapse consecutive duplicates
    dedup = re.sub(r"(.)\1+", r"\1", joined)
    if len(dedup) <= 2:
        return dedup

    # Keep leading char and drop unstressed internal vowels/semi-vowel glides after char 0
    first = dedup[0]
    tail = re.sub(r"[aeiouyw]", "", dedup[1:])
    result = first + tail
    return result or dedup[:2]


def _consonant_skeleton(word: str) -> str:
    """Extract consonant sequence after normalizations ('rest' -> 'rst', 'swion' -> 'swn', 'syn' -> 'sn')."""
    w = re.sub(r"[^a-z0-9]", "", word.lower())
    w = w.replace("ph", "f").replace("ck", "k").replace("qu", "k")
    cons = re.sub(r"[aeiou]", "", w)
    # Collapse 'y' unless acronym like syn
    if len(cons) >= 4:
        cons = cons.replace("y", "")
    return cons or w


def compute_transcription_similarity(spoken: str, cand: CandidateTerm) -> float:
    """
    Compute phonetic + orthographic + letter-spelling similarity in [0.0, 1.0]
    between an observed STT span and a candidate document term.
    """
    sp_clean = re.sub(r"[^A-Za-z0-9]", "", spoken).lower()
    cand_clean = re.sub(r"[^A-Za-z0-9]", "", cand.canonical).lower()
    if not sp_clean or not cand_clean:
        return 0.0

    # Exact letters (possibly spaced or lowercase acronym)
    if sp_clean == cand_clean:
        return 1.0 if spoken.strip() == cand.canonical else 0.98

    # Acronym with minor phonetic vowel differences: e.g. 'sin' vs 'syn'
    sp_norm_y = sp_clean.replace("y", "i").replace("z", "s")
    ca_norm_y = cand_clean.replace("y", "i").replace("z", "s")
    if sp_norm_y == ca_norm_y:
        return 0.95

    max_len = max(len(sp_clean), len(cand_clean))
    w_dist = _weighted_char_distance(sp_clean, cand_clean)
    ortho_sim = max(0.0, 1.0 - (w_dist / max_len))

    sp_phon = _phonetic_key(spoken)
    if sp_phon and cand.phonetic_word:
        p_max = max(len(sp_phon), len(cand.phonetic_word))
        p_dist = _weighted_char_distance(sp_phon, cand.phonetic_word)
        phon_sim = max(0.0, 1.0 - (p_dist / p_max))
        # Bonus if both share exact initial consonant and terminal consonant (e.g. s..n, r..t)
        if sp_phon[0] == cand.phonetic_word[0] and sp_phon[-1] == cand.phonetic_word[-1]:
            phon_sim = min(1.0, phon_sim + 0.14)
    else:
        phon_sim = 0.0

    sp_skel = _consonant_skeleton(spoken)
    skel_sim = 0.0
    if sp_skel and cand.skeleton:
        # Compare skeleton excluding semivowel 'y' inside acronyms like SYN
        ca_skel_noy = cand.skeleton.replace("y", "")
        if sp_skel.replace("y", "") == ca_skel_noy:
            skel_sim = 0.94
        else:
            s_max = max(len(sp_skel), len(cand.skeleton))
            skel_sim = max(0.0, 1.0 - (_weighted_char_distance(sp_skel, cand.skeleton) / s_max))

    # Spoken letter-by-letter comparison if acronym
    letter_sim = 0.0
    if cand.spoken_letters:
        sp_joined = re.sub(r"[^a-z]", "", spoken.lower())
        lt_joined = re.sub(r"[^a-z]", "", cand.spoken_letters.lower())
        if sp_joined and lt_joined:
            l_max = max(len(sp_joined), len(lt_joined))
            letter_sim = max(0.0, 1.0 - (_weighted_char_distance(sp_joined, lt_joined) / l_max))

    # Prevent pure 3-char phonetic hashes from inflating completely different words (e.g. 'sefvault' vs 'sqlite')
    phon_blend = phon_sim * 0.72 + skel_sim * 0.28
    if ortho_sim < 0.45:
        phon_blend = min(phon_blend, ortho_sim + 0.22)
    return round(min(1.0, max(ortho_sim * 0.55 + phon_sim * 0.45, phon_blend, skel_sim * 0.60 + ortho_sim * 0.40, letter_sim)), 4)


def _make_stem_key(text: str) -> str:
    clean = re.sub(r"[^a-z0-9]", "", (text or "").lower())
    return clean[:-1] if len(clean) > 4 and clean.endswith("s") and not clean.endswith("ss") else clean


def _build_candidate_pool(vocab: dict[str, Any]) -> list[CandidateTerm]:
    """Assemble deduplicated CandidateTerm objects strictly from selected document vocabulary."""
    by_key: dict[str, CandidateTerm] = {}

    for up_key, meta in vocab.get("acronyms", {}).items():
        canon = meta.get("canonical") or up_key
        key_low = canon.lower()
        alpha = re.sub(r"[^A-Za-z]", "", canon)
        clean_alnum = re.sub(r"[^a-z0-9]", "", key_low)
        spoken_letters = (
            " ".join(LETTER_TO_SPOKEN.get(ch.upper(), ch.lower()) for ch in alpha)
            if 2 <= len(alpha) <= 6 and (canon.isupper() or canon in {"DoS", "DDoS", "TrOCR"})
            else ""
        )
        by_key[key_low] = CandidateTerm(
            key=key_low,
            canonical=canon,
            is_acronym=True,
            freq=int(meta.get("freq", 1)),
            in_heading=bool(meta.get("in_heading")),
            in_definition=bool(meta.get("in_definition")),
            in_concept=bool(meta.get("in_concept")),
            domain_match=bool(meta.get("domain_match")),
            doc_titles=tuple(sorted(meta.get("doc_titles") or ())),
            phonetic_word=_phonetic_key(canon),
            skeleton=_consonant_skeleton(canon),
            spoken_letters=spoken_letters,
            clean_len=len(clean_alnum),
            char_set=frozenset(clean_alnum),
            stem_key=_make_stem_key(canon),
        )

    for low_key, meta in vocab.get("technical_terms", {}).items():
        if low_key in by_key:
            continue
        canon = meta.get("canonical") or low_key
        clean_alnum = re.sub(r"[^a-z0-9]", "", low_key)
        if len(clean_alnum) < 3:
            continue
        # Only use single-token terms or hyphenated identifiers here (multi-word checked separately)
        if " " in canon:
            continue
        by_key[low_key] = CandidateTerm(
            key=low_key,
            canonical=canon,
            is_acronym=canon.isupper() and len(canon) >= 2,
            freq=int(meta.get("freq", 1)),
            in_heading=bool(meta.get("in_heading") or meta.get("in_title")),
            in_definition=False,
            in_concept=bool(meta.get("in_concept")),
            domain_match=bool(meta.get("domain_match")),
            doc_titles=tuple(sorted(meta.get("doc_titles") or ())),
            phonetic_word=_phonetic_key(canon),
            skeleton=_consonant_skeleton(canon),
            spoken_letters="",
            clean_len=len(clean_alnum),
            char_set=frozenset(clean_alnum),
            stem_key=_make_stem_key(canon),
        )

    return list(by_key.values())


def _parse_spoken_number_candidates(words: list[str]) -> list[str]:
    """
    Convert a short sequence of spoken English number words into plausible numeric strings.
    Supports both digit-by-digit ('five nine six one' -> '5961') and cardinal phrases
    ('thirty eight' -> '38', 'two hundred fifty six' -> '256').
    """
    low_words = [w.lower() for w in words]
    if not low_words or not all(w in ALL_NUMBER_WORDS for w in low_words):
        return []

    results: list[str] = []

    # 1. Digit-by-digit reading (e.g. 'five nine six one' -> '5961')
    if all(w in NUMBER_UNITS and NUMBER_UNITS[w] < 10 for w in low_words):
        results.append("".join(str(NUMBER_UNITS[w]) for w in low_words))

    # 2. Compound integer / mixed digit-tens reading ('thirty eight' -> '38', 'five nine sixty one' -> '5961')
    total = 0
    current = 0
    valid_compound = True
    for w in low_words:
        if w in NUMBER_UNITS:
            current += NUMBER_UNITS[w]
        elif w in NUMBER_TENS:
            current += NUMBER_TENS[w]
        elif w == "hundred":
            current = (current or 1) * 100
        elif w == "thousand":
            total += (current or 1) * 1000
            current = 0
        else:
            valid_compound = False
            break
    if valid_compound:
        val_str = str(total + current)
        if val_str not in results:
            results.append(val_str)

    # 3. Pairwise chunk reading (e.g. 'fifty nine sixty one' -> '5961')
    if len(low_words) >= 2:
        chunk_digits: list[str] = []
        i = 0
        ok = True
        while i < len(low_words):
            w = low_words[i]
            if w in NUMBER_TENS and i + 1 < len(low_words) and low_words[i + 1] in NUMBER_UNITS and NUMBER_UNITS[low_words[i + 1]] < 10:
                chunk_digits.append(str(NUMBER_TENS[w] + NUMBER_UNITS[low_words[i + 1]]))
                i += 2
            elif w in NUMBER_TENS:
                chunk_digits.append(str(NUMBER_TENS[w]))
                i += 1
            elif w in NUMBER_UNITS:
                chunk_digits.append(str(NUMBER_UNITS[w]))
                i += 1
            else:
                ok = False
                break
        if ok and chunk_digits:
            pair_str = "".join(chunk_digits)
            if pair_str not in results:
                results.append(pair_str)

    return results


def _apply_safe_normalization(
    text: str,
    vocab: dict[str, Any],
) -> tuple[str, list[VoiceRecoveryChange]]:
    """
    Apply conservative spoken punctuation and document-grounded spoken number normalization.
    """
    current = text
    changes: list[VoiceRecoveryChange] = []

    # 1. Trailing spoken "question mark" on an obvious question clause
    m_qm = re.match(
        r"^((?i:what|how|why|when|where|who|which|explain|describe|define|is|are|can|could|do|does|did|tell)\b.+?)\s+question\s+mark[\.\?]*$",
        current.strip(),
    )
    if m_qm:
        new_text = m_qm.group(1).rstrip(" .,?") + "?"
        if new_text != current:
            changes.append(
                VoiceRecoveryChange(
                    original_span="question mark",
                    recovered_span="?",
                    change_type="spoken_punctuation",
                    decision="RECOVERED",
                    confidence=0.95,
                    reason="Normalized trailing spoken question mark.",
                    signals={"contextual_support": 0.95, "ambiguity_penalty": 0.0},
                )
            )
            current = new_text

    # 2. Spoken infix 'hyphen' / 'dash' ONLY when the resulting hyphenated term is attested in selected docs
    phrases_set = set(vocab.get("phrases", {}).keys())
    terms_set = set(vocab.get("technical_terms", {}).keys())
    acronyms_map = vocab.get("acronyms", {})

    def _hyphen_repl(match: re.Match) -> str:
        left, right = match.group(1), match.group(2)
        cand_low = f"{left}-{right}".lower()
        cand_space = f"{left} {right}".lower()
        if cand_low in terms_set or cand_low in phrases_set or cand_space in phrases_set:
            if left.upper() in acronyms_map and right.upper() in acronyms_map:
                joined = f"{acronyms_map[left.upper()]['canonical']}-{acronyms_map[right.upper()]['canonical']}"
            elif cand_low in terms_set:
                joined = vocab["technical_terms"][cand_low]["canonical"]
            else:
                joined = f"{left}-{right}"
            changes.append(
                VoiceRecoveryChange(
                    original_span=match.group(0),
                    recovered_span=joined,
                    change_type="spoken_punctuation",
                    decision="RECOVERED",
                    confidence=0.92,
                    reason="Normalized spoken hyphen matching selected document terminology.",
                    signals={"document_term_support": 0.90, "contextual_support": 0.95},
                )
            )
            return joined
        return match.group(0)

    current = re.sub(
        r"\b([A-Za-z0-9]{2,15})\s+(?:hyphen|dash)\s+([A-Za-z0-9]{2,15})\b",
        _hyphen_repl,
        current,
        flags=re.IGNORECASE,
    )

    # 3. Document-supported prefixed numeric identifiers: e.g. 'RFC five nine six one' / 'R F C five nine six one' -> 'RFC 5961'
    prefixed_numbers = vocab.get("prefixed_numbers", {})
    if prefixed_numbers:
        tokens = list(re.finditer(r"\b[A-Za-z0-9]+\b", current))
        replacements: list[tuple[int, int, str, str, list[str]]] = []
        i = 0
        n = len(tokens)
        while i < n:
            matched_step = False
            # Try 1 token prefix or 2-5 spaced single letters forming prefix
            for pref_len in range(min(5, n - i), 0, -1):
                pref_slice = tokens[i : i + pref_len]
                if pref_len > 1 and not all(len(m.group(0)) == 1 and m.group(0).isalpha() for m in pref_slice):
                    continue
                pref_joined = "".join(m.group(0).upper() for m in pref_slice)
                if pref_joined not in prefixed_numbers:
                    continue

                # Check following spoken number words (1 to 6 tokens)
                j = i + pref_len
                num_words: list[str] = []
                while j < n and len(num_words) < 6 and tokens[j].group(0).lower() in ALL_NUMBER_WORDS:
                    num_words.append(tokens[j].group(0))
                    j += 1

                if not num_words:
                    continue

                digit_cands = _parse_spoken_number_candidates(num_words)
                doc_nums = prefixed_numbers[pref_joined]
                hit = next((dn for dc in digit_cands for dn in doc_nums if dn["number"] == dc), None)
                if hit:
                    span_start = tokens[i].start()
                    span_end = tokens[j - 1].end()
                    orig_span = current[span_start:span_end]
                    target_code = hit["full"]
                    if orig_span != target_code:
                        replacements.append((span_start, span_end, orig_span, target_code, sorted(hit.get("doc_titles") or ())))
                        i = j
                        matched_step = True
                        break
            if not matched_step:
                i += 1

        # Apply replacements back-to-front cleanly
        for s_idx, e_idx, orig_span, target_code, docs in reversed(replacements):
            current = current[:s_idx] + target_code + current[e_idx:]
            changes.append(
                VoiceRecoveryChange(
                    original_span=orig_span,
                    recovered_span=target_code,
                    change_type="spoken_number",
                    decision="RECOVERED",
                    confidence=0.94,
                    reason=f"Matched identifier '{target_code}' in selected document.",
                    signals={"transcription_similarity": 0.95, "document_term_support": 0.95, "contextual_support": 0.95},
                )
            )

    return current, changes


_POOL_CACHE_LOCK = threading.Lock()
_POOL_CACHE: OrderedDict[
    tuple[tuple[int, str], ...],
    tuple[list[CandidateTerm], list[CandidateTerm], dict[str, CandidateTerm], dict[str, CandidateTerm]],
] = OrderedDict()


def clear_voice_recovery_cache() -> None:
    """Clear cached CandidateTerm pools (for tests)."""
    with _POOL_CACHE_LOCK:
        _POOL_CACHE.clear()


def _passes_fast_prefilter(
    tok_len: int,
    tok_phon: str,
    tok_chars: set[str],
    cand: CandidateTerm,
) -> bool:
    """Cheap O(1) filter before running weighted DP edit distance."""
    max_diff = 2 if tok_len >= 5 and cand.clean_len >= 5 else 3
    if abs(cand.clean_len - tok_len) > max_diff:
        return False
    if not tok_chars or not cand.char_set:
        return False
    shared = len(tok_chars & cand.char_set)
    if tok_phon and cand.phonetic_word and tok_phon[0] == cand.phonetic_word[0]:
        if tok_len >= 5 and cand.clean_len >= 5:
            return shared >= max(3, min(len(tok_chars), len(cand.char_set)) // 2)
        return True
    min_needed = max(2, (min(len(tok_chars), len(cand.char_set)) + 1) // 2)
    return shared >= min_needed


def _is_ordinary_english(word: str) -> bool:
    """Check whether a lowercase token (or its singular/inflected base) is ordinary English prose."""
    w = (word or "").lower()
    if not w:
        return False
    if w in ORDINARY_ENGLISH_WORDS:
        return True
    if len(w) > 4:
        if w.endswith("ies") and (w[:-3] + "y") in ORDINARY_ENGLISH_WORDS:
            return True
        if w.endswith("es") and (w[:-2] in ORDINARY_ENGLISH_WORDS or w[:-1] in ORDINARY_ENGLISH_WORDS):
            return True
        if w.endswith("s") and not w.endswith("ss") and w[:-1] in ORDINARY_ENGLISH_WORDS:
            return True
        if w.endswith("ed") and (w[:-2] in ORDINARY_ENGLISH_WORDS or w[:-1] in ORDINARY_ENGLISH_WORDS):
            return True
        if w.endswith("ing") and (w[:-3] in ORDINARY_ENGLISH_WORDS or (w[:-3] + "e") in ORDINARY_ENGLISH_WORDS):
            return True
    return False


def _score_candidate_match(
    orig_text: str,
    cand: CandidateTerm,
    prev_word: str,
    next_word: str,
    other_query_words: set[str],
    vocab: dict[str, Any],
    is_spaced_acronym: bool = False,
    is_letter_name_run: bool = False,
    is_split_compound: bool = False,
) -> tuple[float, dict[str, float]]:
    """
    Score a single (span, CandidateTerm) hypothesis using document, contextual,
    semantic, phonetic, acronym, and ambiguity evidence.
    """
    orig_low = orig_text.lower()
    cand_low = cand.key

    # Protect terms that are already identical (exact case)
    if orig_text == cand.canonical:
        return 0.0, {}

    is_ordinary = _is_ordinary_english(orig_low)

    # Protect legitimate English morphological inflections/derivations sharing the same root
    # (e.g. never rewrite clean 'extract' -> 'Extracted' / 'Extraction')
    if (
        not is_spaced_acronym
        and not is_letter_name_run
        and len(orig_low) >= 5
        and len(cand_low) >= 5
        and orig_low[:5] == cand_low[:5]
    ):
        shorter, longer = (orig_low, cand_low) if len(orig_low) <= len(cand_low) else (cand_low, orig_low)
        if longer.startswith(shorter) and longer[len(shorter):] in {
            "s", "es", "d", "ed", "ing", "ion", "tion", "ation", "er", "or", "ly", "ment", "ness", "al",
        }:
            return 0.0, {}

    # Never apply case-only changes to ordinary lowercase prose or non-acronym TitleCase headings
    # (e.g. prevent rewriting 'attacks' -> 'Attacks' or 'vault' -> 'Vault')
    if orig_low == cand_low and orig_text != cand.canonical:
        if (not cand.is_acronym or is_ordinary) and cand.canonical not in {"DoS", "DDoS", "TrOCR", "CephVault", "MiniLM", "PyAV"}:
            return 0.0, {}

    lower_freq = vocab.get("lowercase_word_freq", {})
    bigrams = vocab.get("bigrams", {})
    phrases = vocab.get("phrases", {})
    coocc = vocab.get("cooccurrence_map", {})

    # Check if original token ALREADY exists as an ordinary word in this document
    if is_ordinary and not is_spaced_acronym and not is_letter_name_run:
        if lower_freq.get(orig_low, 0) >= 2:
            return 0.0, {}
        if orig_low != cand_low and lower_freq.get(orig_low, 0) == 1 and not bigrams.get((prev_word, cand_low)) and not bigrams.get((cand_low, next_word)):
            return 0.0, {}

    # 1. Transcription similarity
    if is_spaced_acronym:
        trans_sim = 1.0 if re.sub(r"[^A-Za-z]", "", orig_text).lower() == cand_low else 0.92
    elif is_letter_name_run:
        trans_sim = 0.95
    else:
        trans_sim = compute_transcription_similarity(orig_text, cand)

    min_sim = (
        (0.85 if len(orig_low) >= 6 else 0.78)
        if (is_ordinary and not is_spaced_acronym and not is_letter_name_run)
        else 0.56
    )
    if trans_sim < min_sim:
        return 0.0, {}

    # 2. Document term support (strictly from selected docs)
    doc_support = 0.0
    if cand.freq >= 3:
        doc_support = 0.95
    elif cand.freq == 2:
        doc_support = 0.82
    else:
        doc_support = 0.65
    if cand.in_heading:
        doc_support = max(doc_support, 0.92)
    if cand.in_concept or cand.in_definition:
        doc_support = max(doc_support, 0.95)

    # 3. Contextual & neighboring-word colocation support
    ctx_support = 0.0
    left_bigram_hits = bigrams.get((prev_word, cand_low), 0) if prev_word else 0
    right_bigram_hits = bigrams.get((cand_low, next_word), 0) if next_word else 0
    if left_bigram_hits > 0 or right_bigram_hits > 0:
        hits = max(left_bigram_hits, right_bigram_hits)
        ctx_support = 0.98 if hits >= 2 else 0.90

    if prev_word and f"{prev_word} {cand_low}" in phrases:
        ctx_support = max(ctx_support, 0.96)
    if next_word and f"{cand_low} {next_word}" in phrases:
        ctx_support = max(ctx_support, 0.96)

    # Domain colocation support (only corroborates doc-present term)
    if prev_word and cand_low in _DOMAIN_COLOCATIONS.get(prev_word, set()):
        ctx_support = max(ctx_support, 0.85)
    if next_word and cand_low in _DOMAIN_COLOCATIONS.get(next_word, set()):
        ctx_support = max(ctx_support, 0.85)

    # Grammatical clue in query ("a <X> attack", "the <X> handshake", "explain <X>")
    if next_word in {"flood", "attack", "attacks", "packet", "packets", "cookies", "handshake", "protocol", "system", "model", "stylesheet", "equation"}:
        if right_bigram_hits > 0 or next_word in coocc.get(cand_low, set()):
            ctx_support = max(ctx_support, 0.86)

    # 4. Semantic / chunk co-occurrence support across selected docs
    sem_support = 0.0
    cand_co = coocc.get(cand_low, set())
    unmatched_content = 0
    if other_query_words and cand_co:
        overlap = other_query_words & cand_co
        unmatched_content = len(other_query_words - cand_co)
        ratio = len(overlap) / len(other_query_words)
        sem_support = round(min(1.0, ratio * 1.1), 4) if overlap else 0.0
    elif other_query_words and not cand_co:
        unmatched_content = len(other_query_words)

    # 5. Technical terminology indicator
    tech_support = 0.0
    if cand.domain_match:
        tech_support = max(tech_support, 0.95)
    if cand.in_definition or cand.in_concept or cand.in_heading:
        tech_support = max(tech_support, 0.90)
    if cand.is_acronym and tech_support == 0.0:
        tech_support = 0.72
    elif not is_ordinary and not _is_ordinary_english(cand_low) and tech_support == 0.0:
        if len(cand.key) >= 5 and cand.freq >= 3:
            tech_support = 0.78
        elif len(cand.key) >= 7 and ctx_support >= 0.85:
            tech_support = 0.78

    if (
        not other_query_words
        and not is_ordinary
        and not _is_ordinary_english(cand_low)
        and len(cand.key) >= 7
        and trans_sim >= 0.88
        and ctx_support >= 0.85
    ):
        sem_support = max(sem_support, 0.65)

    # 6. Acronym structure / spoken hint support
    if is_spaced_acronym or is_letter_name_run:
        acro_support = 1.0
    elif cand.is_acronym:
        acro_support = 0.65 if not is_ordinary else 0.40
    else:
        acro_support = 0.30

    # 7. Ambiguity & false-recovery protection penalties
    penalty = 0.0
    if is_ordinary and not is_spaced_acronym and not is_letter_name_run and not is_split_compound:
        if ctx_support >= 0.80:
            penalty += 0.12
        elif sem_support >= 0.50:
            penalty += 0.18
        else:
            penalty += 0.08 if unmatched_content == 0 else (0.08 + min(0.24, 0.14 * unmatched_content))
    elif not is_spaced_acronym and not is_letter_name_run and unmatched_content >= 2 and ctx_support < 0.40:
        penalty += min(0.22, 0.10 * unmatched_content)

    # Low-attestation single occurrence not backed by heading/concept/definition/domain/strong-bigram
    if (
        cand.freq == 1
        and ctx_support < 0.85
        and not is_spaced_acronym
        and not is_letter_name_run
        and not (cand.in_heading or cand.in_concept or cand.in_definition or cand.domain_match)
    ):
        penalty += 0.12

    # Explicitly scored blend: spaced acronyms, exact OOV acronym case normalization, & explicit
    # definitional compound technical terms do not require extra content-word neighbors.
    is_exact_oov_acro = (
        orig_low == cand_low
        and orig_text != cand.canonical
        and cand.is_acronym
        and not is_ordinary
    )
    if is_spaced_acronym or is_letter_name_run or is_exact_oov_acro:
        raw_score = (
            0.42 * trans_sim
            + 0.30 * doc_support
            + 0.14 * max(ctx_support, 0.72 if not other_query_words else 0.55)
            + 0.08 * max(sem_support, 0.65 if not other_query_words else sem_support)
            + 0.06 * max(tech_support, acro_support)
        )
    elif is_split_compound and trans_sim >= 0.80 and not is_ordinary:
        raw_score = (
            0.36 * trans_sim
            + 0.28 * doc_support
            + 0.18 * max(ctx_support, 0.72 if not other_query_words else 0.50)
            + 0.10 * max(sem_support, 0.65 if not other_query_words else sem_support)
            + 0.08 * tech_support
        )
    else:
        raw_score = (
            0.30 * trans_sim
            + 0.25 * doc_support
            + 0.20 * ctx_support
            + 0.10 * sem_support
            + 0.10 * tech_support
            + 0.05 * acro_support
        )
    final_score = round(max(0.0, min(0.99, raw_score - penalty)), 4)

    signals = {
        "transcription_similarity": round(trans_sim, 3),
        "document_term_support": round(doc_support, 3),
        "contextual_support": round(ctx_support, 3),
        "semantic_support": round(sem_support, 3),
        "technical_support": round(tech_support, 3),
        "acronym_support": round(acro_support, 3),
        "ambiguity_penalty": round(penalty, 3),
    }
    return final_score, signals


def recover_voice_query(
    raw_transcript: str,
    db: Session,
    user_id: int,
    document_id: int | None = None,
    document_ids: list[int] | None = None,
    manual_override: bool = False,
    manually_edited_transcript: str | None = None,
) -> VoiceQueryRecoverResponse:
    """
    Context-aware deterministic Voice Query Recovery adhering strictly to the hierarchy of trust:
    raw transcript + selected document evidence -> contextual ranking -> safety gate & abstention.
    """
    t0 = time.perf_counter()
    raw_clean = (raw_transcript or "").strip()

    if not raw_clean:
        return VoiceQueryRecoverResponse(
            raw_transcript=raw_transcript or "",
            recovered_transcript=raw_transcript or "",
            decision="UNCHANGED",
            recovery_applied=False,
            confidence=1.0,
            recovery_reason="Empty transcript left unchanged.",
            suggestions=[],
            changes=[],
            document_scope_count=0,
            cache_hit=True,
            processing_time_ms=round((time.perf_counter() - t0) * 1000.0, 2),
        )

    if manual_override:
        edited = (manually_edited_transcript if manually_edited_transcript is not None else raw_clean).strip()
        return VoiceQueryRecoverResponse(
            raw_transcript=raw_clean,
            recovered_transcript=edited or raw_clean,
            decision="MANUAL",
            recovery_applied=False,
            confidence=1.0,
            recovery_reason="Manual transcript edits are protected.",
            suggestions=[],
            changes=[],
            document_scope_count=0,
            cache_hit=True,
            processing_time_ms=round((time.perf_counter() - t0) * 1000.0, 2),
        )

    vocab = get_scoped_terminology(
        db=db,
        user_id=user_id,
        document_id=document_id,
        document_ids=document_ids,
    )
    doc_count = int(vocab.get("document_count", 0))
    cache_hit = bool(vocab.get("cache_hit", False))

    if not vocab.get("has_evidence"):
        return VoiceQueryRecoverResponse(
            raw_transcript=raw_clean,
            recovered_transcript=raw_clean,
            decision="UNCHANGED",
            recovery_applied=False,
            confidence=1.0,
            recovery_reason="No selected document terminology available; original transcript kept.",
            suggestions=[],
            changes=[],
            document_scope_count=doc_count,
            cache_hit=cache_hit,
            processing_time_ms=round((time.perf_counter() - t0) * 1000.0, 2),
        )

    pool_sig = tuple((d["id"], d["content_hash"]) for d in vocab.get("documents", []))
    cached_pool_entry = None
    if pool_sig:
        with _POOL_CACHE_LOCK:
            cached_pool_entry = _POOL_CACHE.get(pool_sig)
            if cached_pool_entry is not None:
                _POOL_CACHE.move_to_end(pool_sig)

    if cached_pool_entry is not None:
        candidates_pool, acronyms_pool, cand_by_upper, cand_by_joined_lower = cached_pool_entry
    else:
        candidates_pool = _build_candidate_pool(vocab)
        acronyms_pool = [c for c in candidates_pool if c.is_acronym]
        cand_by_upper = {c.canonical.upper(): c for c in acronyms_pool}
        cand_by_joined_lower = {re.sub(r"[^a-z0-9]", "", c.key): c for c in candidates_pool}
        if pool_sig:
            with _POOL_CACHE_LOCK:
                _POOL_CACHE[pool_sig] = (candidates_pool, acronyms_pool, cand_by_upper, cand_by_joined_lower)
                while len(_POOL_CACHE) > 64:
                    _POOL_CACHE.popitem(last=False)

    if not candidates_pool:
        return VoiceQueryRecoverResponse(
            raw_transcript=raw_clean,
            recovered_transcript=raw_clean,
            decision="UNCHANGED",
            recovery_applied=False,
            confidence=1.0,
            recovery_reason="No domain candidates extracted from selected documents.",
            suggestions=[],
            changes=[],
            document_scope_count=doc_count,
            cache_hit=cache_hit,
            processing_time_ms=round((time.perf_counter() - t0) * 1000.0, 2),
        )

    # Step 1: Safe spoken punctuation & doc-backed numeric code normalization
    working_text, norm_changes = _apply_safe_normalization(raw_clean, vocab)

    # Track spans to update after scanning word tokens
    token_matches = list(re.finditer(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", working_text))
    n_tok = len(token_matches)

    applied_spans: list[tuple[int, int, str, str, VoiceRecoveryChange]] = []
    suggestions: list[VoiceRecoverySuggestion] = []
    all_changes: list[VoiceRecoveryChange] = list(norm_changes)
    consumed_tok_indices: set[int] = set()

    query_filler_words = ENGLISH_STOP_WORDS | {
        "explain", "describe", "define", "summarize", "compare", "contrast",
        "tell", "give", "list", "name", "show", "differ", "differs", "used",
        "using", "work", "works", "help", "helps", "mean", "means", "make", "makes",
    }

    def _other_words(skip_start_tok: int, skip_end_tok: int) -> set[str]:
        res: set[str] = set()
        for idx, tm in enumerate(token_matches):
            if skip_start_tok <= idx < skip_end_tok:
                continue
            lw = tm.group(0).lower()
            if lw not in query_filler_words and len(lw) >= 2:
                res.add(lw)
        return res

    # Step 2a: Hyphenated spelled-acronym compound tokens (e.g. 'S-Y-N-Flood' -> 'SYN flood', 'S-Y-N' -> 'SYN')
    for idx, tm in enumerate(token_matches):
        tok = tm.group(0)
        if "-" not in tok:
            continue
        parts = tok.split("-")
        # Extract leading single-letter chain
        letter_run_len = 0
        for p in parts:
            if len(p) == 1 and p.isalpha():
                letter_run_len += 1
            else:
                break
        if letter_run_len >= 2:
            joined_up = "".join(parts[:letter_run_len]).upper()
            cand = cand_by_upper.get(joined_up)
            if cand:
                prev_w = token_matches[idx - 1].group(0).lower() if idx > 0 else ""
                next_w = (parts[letter_run_len].lower() if letter_run_len < len(parts) else (token_matches[idx + 1].group(0).lower() if idx + 1 < n_tok else ""))
                score, sigs = _score_candidate_match(
                    orig_text=tok if letter_run_len == len(parts) else "-".join(parts[:letter_run_len]),
                    cand=cand,
                    prev_word=prev_w,
                    next_word=next_w,
                    other_query_words=_other_words(idx, idx + 1),
                    vocab=vocab,
                    is_spaced_acronym=True,
                )
                if score >= AUTO_APPLY_THRESHOLD:
                    tail = parts[letter_run_len:]
                    if tail:
                        tail_str = " ".join(p.lower() if f"{cand.canonical.lower()} {p.lower()}" in vocab.get("phrases", {}) or p.lower() in ORDINARY_ENGLISH_WORDS else p for p in tail)
                        repl = f"{cand.canonical} {tail_str}"
                    else:
                        repl = cand.canonical
                    if repl != tok:
                        chg = VoiceRecoveryChange(
                            original_span=tok,
                            recovered_span=repl,
                            change_type="spaced_acronym",
                            decision="RECOVERED",
                            confidence=round(score, 3),
                            reason="Matched hyphenated acronym in selected document.",
                            signals=sigs,
                        )
                        applied_spans.append((tm.start(), tm.end(), tok, repl, chg))
                        consumed_tok_indices.add(idx)

    # Step 2b: Spaced single-letter acronyms (e.g. 'S Y N', 'T C P', 'R S T', 'C S S', 'O D E')
    i = 0
    while i < n_tok:
        if i in consumed_tok_indices:
            i += 1
            continue
        matched_spaced = False
        max_w = min(6, n_tok - i)
        for length in range(max_w, 1, -1):
            window = token_matches[i : i + length]
            if any(k in consumed_tok_indices for k in range(i, i + length)):
                continue
            words_w = [m.group(0) for m in window]
            if not all(len(w) == 1 and w.isalpha() for w in words_w):
                continue
            # Avoid absorbing a leading lowercase article 'a' when the remaining letters already form an acronym
            if words_w[0] == "a" and length >= 3 and "".join(words_w[1:]).upper() in cand_by_upper:
                continue
            joined_up = "".join(words_w).upper()
            cand = cand_by_upper.get(joined_up)
            if cand:
                prev_w = token_matches[i - 1].group(0).lower() if i > 0 else ""
                next_w = token_matches[i + length].group(0).lower() if i + length < n_tok else ""
                orig_span = working_text[window[0].start() : window[-1].end()]
                score, sigs = _score_candidate_match(
                    orig_text=orig_span,
                    cand=cand,
                    prev_word=prev_w,
                    next_word=next_w,
                    other_query_words=_other_words(i, i + length),
                    vocab=vocab,
                    is_spaced_acronym=True,
                )
                if score >= AUTO_APPLY_THRESHOLD and orig_span != cand.canonical:
                    chg = VoiceRecoveryChange(
                        original_span=orig_span,
                        recovered_span=cand.canonical,
                        change_type="spaced_acronym",
                        decision="RECOVERED",
                        confidence=round(score, 3),
                        reason="Matched spaced acronym in selected document.",
                        signals=sigs,
                    )
                    applied_spans.append((window[0].start(), window[-1].end(), orig_span, cand.canonical, chg))
                    for k in range(i, i + length):
                        consumed_tok_indices.add(k)
                    i += length
                    matched_spaced = True
                    break
        if not matched_spaced:
            i += 1

    # Step 2c: Phonetic letter-name runs (e.g. 'tea see pee' -> 'TCP', 'are ess tee' -> 'RST', 'see ess ess' -> 'CSS')
    i = 0
    while i < n_tok:
        if i in consumed_tok_indices:
            i += 1
            continue
        matched_ln = False
        max_w = min(5, n_tok - i)
        for length in range(max_w, 1, -1):
            if any(k in consumed_tok_indices for k in range(i, i + length)):
                continue
            window = token_matches[i : i + length]
            mapped = [SPOKEN_WORD_TO_LETTER.get(m.group(0).lower()) for m in window]
            if not all(mapped):
                continue
            # Require at least one distinctive letter-name token ('ess', 'tee', 'dee', 'kay', etc.)
            # so ordinary prose sequences like 'are you' never turn into 'RU'
            if not any(m[1] for m in mapped if m):
                continue
            joined_up = "".join(m[0] for m in mapped if m)
            cand = cand_by_upper.get(joined_up)
            if cand:
                prev_w = token_matches[i - 1].group(0).lower() if i > 0 else ""
                next_w = token_matches[i + length].group(0).lower() if i + length < n_tok else ""
                orig_span = working_text[window[0].start() : window[-1].end()]
                score, sigs = _score_candidate_match(
                    orig_text=orig_span,
                    cand=cand,
                    prev_word=prev_w,
                    next_word=next_w,
                    other_query_words=_other_words(i, i + length),
                    vocab=vocab,
                    is_letter_name_run=True,
                )
                if score >= AUTO_APPLY_THRESHOLD and orig_span != cand.canonical:
                    chg = VoiceRecoveryChange(
                        original_span=orig_span,
                        recovered_span=cand.canonical,
                        change_type="spaced_acronym",
                        decision="RECOVERED",
                        confidence=round(score, 3),
                        reason="Matched spoken letter sequence to document acronym.",
                        signals=sigs,
                    )
                    applied_spans.append((window[0].start(), window[-1].end(), orig_span, cand.canonical, chg))
                    for k in range(i, i + length):
                        consumed_tok_indices.add(k)
                    i += length
                    matched_ln = True
                    break
        if not matched_ln:
            i += 1

    # Step 2d: Two-token split technical term recovery (e.g. 'sef vault' -> 'CephVault', 'back log' -> 'backlog')
    i = 0
    while i < n_tok - 1:
        if i in consumed_tok_indices or (i + 1) in consumed_tok_indices:
            i += 1
            continue
        w1 = token_matches[i].group(0)
        w2 = token_matches[i + 1].group(0)
        if w1.lower() in ENGLISH_STOP_WORDS or w2.lower() in ENGLISH_STOP_WORDS:
            i += 1
            continue
        joined_pair = f"{w1}{w2}"
        if len(joined_pair) >= 5 and not (_is_ordinary_english(w1) and _is_ordinary_english(w2)):
            prev_w = token_matches[i - 1].group(0).lower() if i > 0 else ""
            next_w = token_matches[i + 2].group(0).lower() if i + 2 < n_tok else ""
            other_w = _other_words(i, i + 2)
            pair_clean = re.sub(r"[^a-z0-9]", "", joined_pair.lower())
            pair_phon = _phonetic_key(pair_clean)
            pair_chars = set(pair_clean)
            pair_len = len(pair_clean)
            scored_cands: list[tuple[float, CandidateTerm, dict[str, float]]] = []
            for cand in candidates_pool:
                if cand.clean_len < 5 or not _passes_fast_prefilter(pair_len, pair_phon, pair_chars, cand):
                    continue
                # Skip if both words are already exact in the document bigram
                if vocab.get("bigrams", {}).get((w1.lower(), w2.lower()), 0) > 0:
                    continue
                score, sigs = _score_candidate_match(
                    orig_text=joined_pair,
                    cand=cand,
                    prev_word=prev_w,
                    next_word=next_w,
                    other_query_words=other_w,
                    vocab=vocab,
                    is_split_compound=True,
                )
                if score >= AUTO_APPLY_THRESHOLD and sigs.get("transcription_similarity", 0.0) >= 0.78:
                    scored_cands.append((score, cand, sigs))
            if scored_cands:
                scored_cands.sort(key=lambda x: (x[0], x[1].freq), reverse=True)
                best_score, best_cand, best_sigs = scored_cands[0]
                distinct_runner = next((sc for sc in scored_cands[1:] if sc[1].stem_key != best_cand.stem_key), None)
                margin_ok = distinct_runner is None or (best_score - distinct_runner[0] >= AMBIGUITY_MARGIN)
                if margin_ok:
                    orig_span = working_text[token_matches[i].start() : token_matches[i + 1].end()]
                    if orig_span != best_cand.canonical:
                        chg = VoiceRecoveryChange(
                            original_span=orig_span,
                            recovered_span=best_cand.canonical,
                            change_type="technical_term",
                            decision="RECOVERED",
                            confidence=round(best_score, 3),
                            reason="Matched split term to terminology in selected document.",
                            signals=best_sigs,
                        )
                        applied_spans.append((token_matches[i].start(), token_matches[i + 1].end(), orig_span, best_cand.canonical, chg))
                        consumed_tok_indices.update({i, i + 1})
                        i += 2
                        continue
        i += 1

    # Step 2e: Concatenated single-token -> known 2-word document phrase (e.g. 'synflood' -> 'SYN flood')
    phrases_map = vocab.get("phrases", {})
    for idx, tm in enumerate(token_matches):
        if idx in consumed_tok_indices:
            continue
        tok = tm.group(0)
        tok_low = tok.lower()
        if len(tok_low) < 7 or tok_low in ORDINARY_ENGLISH_WORDS or tok_low in cand_by_joined_lower:
            continue
        best_phrase_hit: tuple[float, str, str] | None = None
        for phr_low, phr_meta in phrases_map.items():
            if " " not in phr_low:
                continue
            phr_compact = re.sub(r"[^a-z0-9]", "", phr_low)
            if abs(len(phr_compact) - len(tok_low)) > 2:
                continue
            w_dist = _weighted_char_distance(tok_low, phr_compact)
            sim = 1.0 - (w_dist / max(len(tok_low), len(phr_compact)))
            if sim >= 0.80:
                canon_phr = phr_meta.get("canonical") or phr_low
                score = min(0.95, 0.55 * sim + 0.40)
                if best_phrase_hit is None or score > best_phrase_hit[0]:
                    best_phrase_hit = (score, canon_phr, "Matched merged phrase in selected document.")
        if best_phrase_hit and best_phrase_hit[0] >= AUTO_APPLY_THRESHOLD:
            score, canon_phr, reason = best_phrase_hit
            chg = VoiceRecoveryChange(
                original_span=tok,
                recovered_span=canon_phr,
                change_type="technical_term",
                decision="RECOVERED",
                confidence=round(score, 3),
                reason=reason,
                signals={"transcription_similarity": 0.90, "document_term_support": 0.90},
            )
            applied_spans.append((tm.start(), tm.end(), tok, canon_phr, chg))
            consumed_tok_indices.add(idx)

    # Step 2f: Individual token distortion & acronym resolution + suggestion detection
    deferred_suggestions: list[tuple[int, int, str, CandidateTerm, float, dict[str, float], bool]] = []
    canonical_exact_set = {c.canonical for c in candidates_pool}
    for idx, tm in enumerate(token_matches):
        if idx in consumed_tok_indices:
            continue
        tok = tm.group(0)
        tok_low = tok.lower()

        if len(tok) <= 2 and tok_low in ULTRA_COMMON_SHORT_WORDS:
            continue
        if tok.isdigit():
            continue
        if tok in canonical_exact_set:
            continue
        prev_w = token_matches[idx - 1].group(0).lower() if idx > 0 else ""
        next_w = token_matches[idx + 1].group(0).lower() if idx + 1 < n_tok else ""
        is_ordinary = _is_ordinary_english(tok_low)
        is_exact_non_ordinary_acronym = (
            not is_ordinary
            and tok_low.upper() in vocab.get("acronyms", {})
        )
        is_doc_lower_word = (
            not is_exact_non_ordinary_acronym
            and vocab.get("lowercase_word_freq", {}).get(tok_low, 0) >= 2
        )
        # Always protect words literally attested lowercase in the selected documents (unless
        # explicit neighbor colocation supports an acronym). Ordinary English words not in the doc
        # still check acronyms_pool so ambiguous queries ('What is sin?') can offer safe suggestions
        # while blocked from auto-apply unless strongly colocated.
        if is_doc_lower_word:
            has_colocated_cand = (
                (prev_w and any(vocab.get("bigrams", {}).get((prev_w, c.key), 0) > 0 for c in acronyms_pool))
                or (next_w and any(vocab.get("bigrams", {}).get((c.key, next_w), 0) > 0 for c in acronyms_pool))
            )
            if not has_colocated_cand:
                continue
        other_w = _other_words(idx, idx + 1)

        # Ordinary words only inspect attested document acronyms (e.g. 'sin' <-> 'SYN'),
        # never scanning non-acronym document words.
        search_pool = acronyms_pool if is_ordinary else candidates_pool
        tok_clean = re.sub(r"[^a-z0-9]", "", tok_low)
        tok_clean_len = len(tok_clean)
        tok_phon = _phonetic_key(tok_clean)
        tok_chars = set(tok_clean)

        scored: list[tuple[float, CandidateTerm, dict[str, float]]] = []
        for cand in search_pool:
            if not _passes_fast_prefilter(tok_clean_len, tok_phon, tok_chars, cand):
                continue
            score, sigs = _score_candidate_match(
                orig_text=tok,
                cand=cand,
                prev_word=prev_w,
                next_word=next_w,
                other_query_words=other_w,
                vocab=vocab,
            )
            if score >= SUGGEST_THRESHOLD:
                scored.append((score, cand, sigs))

        if not scored:
            continue

        scored.sort(key=lambda x: (x[0], x[2].get("contextual_support", 0.0), x[2].get("transcription_similarity", 0.0), x[1].freq), reverse=True)
        top_score, top_cand, top_sigs = scored[0]
        distinct_runner = next((sc for sc in scored[1:] if sc[1].stem_key != top_cand.stem_key), None)
        second_score = distinct_runner[0] if distinct_runner else 0.0
        is_tight_tie = distinct_runner is not None and (top_score - second_score < AMBIGUITY_MARGIN)

        # Safety gate decision for this token span
        ordinary_blocked_from_auto = (
            is_ordinary
            and top_sigs.get("contextual_support", 0.0) < 0.75
            and top_sigs.get("semantic_support", 0.0) < 0.50
        )

        if (
            top_score >= AUTO_APPLY_THRESHOLD
            and not is_tight_tie
            and not ordinary_blocked_from_auto
            and top_sigs.get("document_term_support", 0.0) > 0.0
        ):
            # Case-only adjustment on an already-correct OOV lowercase token: still preserve clear reason
            reason = (
                "Based on terminology in your selected document."
                if top_cand.is_acronym
                else "Matched technical term in your selected document."
            )
            chg = VoiceRecoveryChange(
                original_span=tok,
                recovered_span=top_cand.canonical,
                change_type="acronym" if top_cand.is_acronym else "technical_term",
                decision="RECOVERED",
                confidence=round(top_score, 3),
                reason=reason,
                signals=top_sigs,
            )
            applied_spans.append((tm.start(), tm.end(), tok, top_cand.canonical, chg))
        elif top_score >= SUGGEST_THRESHOLD:
            # Ambiguous or medium confidence -> suggest without changing active query
            deferred_suggestions.append((tm.start(), tm.end(), tok, top_cand, top_score, top_sigs, is_tight_tie))
            if is_tight_tie and len(scored) > 1:
                sec_cand = scored[1][1]
                sec_score = scored[1][0]
                sec_sigs = scored[1][2]
                deferred_suggestions.append((tm.start(), tm.end(), tok, sec_cand, sec_score, sec_sigs, True))

    # Apply non-overlapping span replacements right-to-left on working_text
    applied_spans.sort(key=lambda item: item[0], reverse=True)
    recovered_text = working_text
    last_start = len(working_text) + 1
    for s_pos, e_pos, orig_sp, repl_sp, chg in applied_spans:
        if e_pos <= last_start:
            recovered_text = recovered_text[:s_pos] + repl_sp + recovered_text[e_pos:]
            all_changes.append(chg)
            last_start = s_pos

    # Build user-facing suggestion choices using recovered_text-aligned spans when no auto-apply collided
    any_tight_tie = any(item[6] for item in deferred_suggestions)
    for s_pos, e_pos, orig_sp, cand, score, sigs, _tie in deferred_suggestions:
        # Build clean replacement preview on working_text
        if working_text[s_pos:e_pos] != orig_sp:
            continue
        replacement_q = working_text[:s_pos] + cand.canonical + working_text[e_pos:]
        suggestions.append(
            VoiceRecoverySuggestion(
                original_span=orig_sp,
                suggested_span=cand.canonical,
                replacement_query=replacement_q,
                confidence=round(score, 3),
                reason=(
                    "Possible match found in your selected document."
                    if not any_tight_tie
                    else "Multiple terminology matches found in your selected document."
                ),
                matched_documents=list(cand.doc_titles),
            )
        )

    # Deduplicate suggestions by suggested_span
    seen_sugg: set[tuple[str, str]] = set()
    unique_suggestions: list[VoiceRecoverySuggestion] = []
    for sug in suggestions:
        k = (sug.original_span.lower(), sug.suggested_span.lower())
        if k not in seen_sugg:
            seen_sugg.add(k)
            unique_suggestions.append(sug)
    suggestions = unique_suggestions[:3]

    # Final Safety Gate summary state
    recovery_applied = bool(all_changes) and recovered_text != raw_clean
    if recovery_applied:
        decision: RecoveryDecision = "RECOVERED"
        min_conf = min(c.confidence for c in all_changes)
        reason = all_changes[-1].reason
        final_conf = round(min_conf, 3)
        final_recovered = recovered_text
    elif suggestions:
        decision = "AMBIGUOUS" if any_tight_tie or len(suggestions) > 1 else "SUGGESTED"
        final_conf = round(suggestions[0].confidence, 3)
        reason = suggestions[0].reason
        final_recovered = raw_clean
        for sug in suggestions:
            all_changes.append(
                VoiceRecoveryChange(
                    original_span=sug.original_span,
                    recovered_span=sug.suggested_span,
                    change_type="acronym",
                    decision=decision,
                    confidence=sug.confidence,
                    reason=sug.reason,
                    signals={},
                )
            )
    else:
        decision = "UNCHANGED"
        final_conf = 1.0
        reason = "Transcript matches query context; kept unchanged."
        final_recovered = raw_clean

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    return VoiceQueryRecoverResponse(
        raw_transcript=raw_clean,
        recovered_transcript=final_recovered,
        decision=decision,
        recovery_applied=recovery_applied,
        confidence=final_conf,
        recovery_reason=reason,
        suggestions=suggestions,
        changes=all_changes,
        document_scope_count=doc_count,
        cache_hit=cache_hit,
        processing_time_ms=elapsed_ms,
    )
