from app.models import document_chunk
from app.models import document_chunk
from app.models import document_chunk
from app.models import document_chunk
from app.models import document_chunk
from app.models import document_chunk
from networkx.generators import internet_as_graphs
from networkx.generators import internet_as_graphs
import re

from app.services.embedding_services import generate_embedding
from app.services.similarity_service import cosine_similarity
from app.models.document_chunk import DocumentChunk


# --------------------------------------------------
# SEARCH THRESHOLDS / WEIGHTS
# --------------------------------------------------

SIMILARITY_THRESHOLD = 0.20
FINAL_SCORE_THRESHOLD = 0.20

SEMANTIC_WEIGHT = 0.70
KEYWORD_WEIGHT = 0.30


# --------------------------------------------------
# QUERY EXPANSIONS
# --------------------------------------------------

QUERY_EXPANSIONS = {
    "bca": "Bachelor of Computer Applications",
    "mca": "Master of Computer Applications",
}


# --------------------------------------------------
# SPECIFIC QUERY INTENTS
# --------------------------------------------------

QUERY_INTENTS = {
    "programming_languages": [
        "programming language",
        "programming languages",
        "coding language",
        "coding languages",
    ],

    "web_frameworks": [
        "web technology",
        "web technologies",
        "framework",
        "frameworks",
        "web framework",
        "web frameworks",
    ],

    "databases": [
        "database",
        "databases",
        "database management",
    ],

    "tools": [
        "tools",
        "tools and platforms",
        "tools platforms",
    ],

    "ides": [
        "ide",
        "ides",
        "integrated development environment",
    ],

    "operating_systems": [
        "operating system",
        "operating systems",
    ],

    "technical_skills": [
        "technical skill",
        "technical skills",
    ],

    "certifications": [
        "certification",
        "certifications",
        "certificate",
        "certificates",
    ],

    "projects": [
        "project",
        "projects",
    ],

    "internship": [
        "internship",
        "internships",
        "intern",
    ],

    "workshops": [
        "workshop",
        "workshops",
        "bootcamp",
    ],

    "awards": [
        "award",
        "awards",
        "achievement",
        "achievements",
    ],

    "education": [
        "education",
        "educational",
        "qualification",
        "qualifications",
        "degree",
        "cgpa",
        "percentage",
        "bca",
        "mca",
        "bachelor",
        "master",
    ],

    "languages": [
    "spoken language",
    "spoken languages",
    "human language",
    "human languages",
    "languages known",
    ],

    "ambiguous_languages": [
    "what languages",
    "which languages",
    ]
}


# --------------------------------------------------
# DOCUMENT SECTION MARKERS
# --------------------------------------------------

SECTION_MARKERS = {

    "education": [
        "educational qualifications",
        "higher secondary education",
        "secondary school education",
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

    "languages": [
        "languages known",
    ],

    "certifications": [
        "certifications done",
    ],
}


# --------------------------------------------------
# SPECIFIC SUBSECTION MARKERS
# --------------------------------------------------

SUBSECTION_MARKERS = {

    "programming_languages": [
        "programming languages:",
    ],

    "web_frameworks": [
        "web & frameworks:",
        "web and frameworks:",
    ],

    "databases": [
        "database management:",
        "databases:",
    ],

    "tools": [
        "tools & platforms:",
        "tools and platforms:",
    ],

    "ides": [
        "ides:",
    ],

    "operating_systems": [
        "operating systems:",
    ],
}


# --------------------------------------------------
# QUERY EXPANSION
# --------------------------------------------------

def expand_query(query: str) -> str:
    """
    Expand common abbreviations before generating
    the semantic embedding.
    """

    expanded_query = query

    for abbreviation, full_form in QUERY_EXPANSIONS.items():

        pattern = rf"\b{re.escape(abbreviation)}\b"

        expanded_query = re.sub(
            pattern,
            f"{abbreviation} {full_form}",
            expanded_query,
            flags=re.IGNORECASE
        )

    return expanded_query


# --------------------------------------------------
# QUERY INTENT DETECTION
# --------------------------------------------------

def detect_query_intent(query: str) -> str | None:
    """
    Detect the most specific information requested
    by the user.
    """

    query_lower = query.lower().strip()

    # Most specific categories first
    priority = [
        "programming_languages",
        "web_frameworks",
        "databases",
        "operating_systems",
        "ides",
        "tools",
        "certifications",
        "projects",
        "workshops",
        "awards",
        "education",
        "internship",
        "ambiguous_languages",
        "languages",
        "technical_skills",
    ]

    for intent in priority:

        for keyword in QUERY_INTENTS[intent]:

            if re.search(
                rf"\b{re.escape(keyword)}\b",
                query_lower
            ):
                return intent

    return None

def is_ambiguous_language_query(query: str) -> bool:
    """
    Detect questions that ask generally about "languages"
    without specifying programming or spoken languages.
    """

    query_lower = query.lower().strip()

    # Explicit programming-language queries are not ambiguous
    programming_phrases = [
        "programming language",
        "programming languages",
        "coding language",
        "coding languages",
    ]

    # Explicit spoken-language queries are not ambiguous
    spoken_phrases = [
        "spoken language",
        "spoken languages",
        "human language",
        "human languages",
    ]

    if any(
        phrase in query_lower
        for phrase in programming_phrases + spoken_phrases
    ):
        return False

    # General language question
    return bool(
        re.search(r"\bwhat languages\b", query_lower)
        or re.search(r"\bwhich languages\b", query_lower)
        or re.search(r"\blanguages does\b", query_lower)
    )

# --------------------------------------------------
# BACKWARD COMPATIBILITY
# --------------------------------------------------

def detect_query_category(query: str) -> str | None:
    """
    Return the broader document category.

    This keeps compatibility with existing code.
    """

    intent = detect_query_intent(query)

    if intent in {
        "programming_languages",
        "web_frameworks",
        "databases",
        "tools",
        "ides",
        "operating_systems",
        "technical_skills",
    }:
        return "technical_skills"

    return intent


# --------------------------------------------------
# QUERY CONTEXT
# --------------------------------------------------

def detect_query_context(query: str) -> str | None:
    """
    Detect contextual constraints in the user's question.
    """

    query_lower = query.lower()

    internship_phrases = [
        "during their internship",
        "during the internship",
        "in their internship",
        "in the internship",
        "while doing their internship",
        "while on their internship",
        "as part of their internship",
    ]

    for phrase in internship_phrases:

        if phrase in query_lower:
            return "internship"

    return None


# --------------------------------------------------
# KEYWORD SCORE
# --------------------------------------------------

def calculate_keyword_score(
    query: str,
    content: str
) -> float:
    """
    Calculate keyword overlap between query and content.
    """

    query_words = set(
        re.findall(
            r"\b[a-zA-Z0-9]+\b",
            query.lower()
        )
    )

    content_words = set(
        re.findall(
            r"\b[a-zA-Z0-9]+\b",
            content.lower()
        )
    )

    if not query_words:
        return 0.0

    matched_words = query_words.intersection(
        content_words
    )

    # Abbreviation/full-form matching
    for abbreviation, full_form in QUERY_EXPANSIONS.items():

        if abbreviation in query_words:

            full_form_words = set(
                re.findall(
                    r"\b[a-zA-Z0-9]+\b",
                    full_form.lower()
                )
            )

            if full_form_words.issubset(content_words):

                matched_words.add(
                    abbreviation
                )

    return len(matched_words) / len(query_words)


# --------------------------------------------------
# CATEGORY BOOST
# --------------------------------------------------

def calculate_category_boost(
    category: str | None,
    content: str
) -> float:
    """
    Boost chunks belonging to the requested
    broad document category.
    """

    if category is None:
        return 0.0

    content_lower = content.lower()

    markers = SECTION_MARKERS.get(
        category,
        []
    )

    matches = 0

    for marker in markers:

        if marker in content_lower:
            matches += 1

    if matches == 0:
        return 0.0

    if matches >= 2:
        return 0.50

    return 0.40


# --------------------------------------------------
# SUBSECTION BOOST
# --------------------------------------------------

def calculate_subsection_boost(
    intent: str | None,
    content: str
) -> float:
    """
    Strongly boost chunks containing the exact
    subsection requested by the user.
    """

    if intent is None:
        return 0.0

    markers = SUBSECTION_MARKERS.get(
        intent,
        []
    )

    if not markers:
        return 0.0

    content_lower = content.lower()

    for marker in markers:

        if marker in content_lower:
            return 0.80

    return 0.0


# --------------------------------------------------
# SEARCH
# --------------------------------------------------

def semantic_search(
    query: str,
    db,
    document_id: int | None = None,
    top_k: int = 5
):
    """
    Perform hybrid semantic + keyword +
    category + subsection search.
    """

    expanded_query = expand_query(query)

    query_embedding = generate_embedding(
        expanded_query
    )

    intent = detect_query_intent(query)

    category = detect_query_category(query)

    query_context = detect_query_context(query)

    ambiguous_language_query = is_ambiguous_language_query(query)

    # Ambiguous "languages" queries should search both
    # programming languages and spoken languages.
    if intent == "ambiguous_languages":
        intent = None
        category = None

    query_db = db.query(DocumentChunk)

    if document_id is not None:

        query_db = query_db.filter(
            DocumentChunk.document_id == document_id
        )

    chunks = query_db.all()

    results = []

    # --------------------------------------------------
    # Ambiguous language query
    # --------------------------------------------------

    if ambiguous_language_query:

        programming_chunks = []
        spoken_language_chunks = []

        for chunk in chunks:

            if not chunk.embedding:
                continue

            content_lower = chunk.content.lower()

            # Programming Languages section
            if "programming languages:" in content_lower:
                programming_chunks.append(chunk)

            # Spoken Languages section
            elif "languages known" in content_lower:
                spoken_language_chunks.append(chunk)

        # Force both language categories into the result set
        special_chunks = (
            programming_chunks +
            spoken_language_chunks
        )

    else:
        special_chunks = []

    # --------------------------------------------------
    # Resolve ambiguous "language" queries
    # --------------------------------------------------

    if ambiguous_language_query:
        query_intent = "languages"
        category = "languages"

    chunks_to_search = special_chunks if ambiguous_language_query else chunks

    for chunk in chunks_to_search:

        if not chunk.embedding:
            continue
        
        # --------------------------------------------------
        # Ambiguous language query boost
        # --------------------------------------------------

        language_category_boost = 0.0

        if ambiguous_language_query:
            content_lower = chunk.content.lower()

            if "languages known" in content_lower:
                language_category_boost = 0.80

            elif "programming languages:" in content_lower:
                language_category_boost = 0.40

        similarity = cosine_similarity(
            query_embedding,
            chunk.embedding
        )

        keyword_score = calculate_keyword_score(
            query,
            chunk.content
        )

        category_boost = calculate_category_boost(
            category,
            chunk.content
        )

        subsection_boost = calculate_subsection_boost(
            intent,
            chunk.content
        )

        # --------------------------------------------------
        # Context filtering
        # --------------------------------------------------

        if query_context == "internship":

            chunk_category = (
                chunk.category or ""
            ).lower()

            if chunk_category != "internship":
                continue

        # --------------------------------------------------
        # Strong subsection filtering
        # --------------------------------------------------


        if intent in SUBSECTION_MARKERS:

            subsection_present = False

            content_lower = chunk.content.lower()

            for marker in SUBSECTION_MARKERS[intent]:

                if marker in content_lower:
                    subsection_present = True
                    break

            # For specific subsection queries, only return
            # chunks that actually contain that subsection.
            if not subsection_present:
                continue

        # --------------------------------------------------
        # General relevance filtering
        # --------------------------------------------------

        if (
            similarity < SIMILARITY_THRESHOLD
            and keyword_score == 0
            and category_boost == 0
            and subsection_boost == 0
        ):
            continue

        # --------------------------------------------------
        # Final score
        # --------------------------------------------------

        final_score = (
            SEMANTIC_WEIGHT * similarity
            + KEYWORD_WEIGHT * keyword_score
            + category_boost
            + subsection_boost
            + language_category_boost
        )

        if final_score >= FINAL_SCORE_THRESHOLD:

            results.append({
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "similarity": similarity,
                "keyword_score": keyword_score,
                "category": category,
                "query_intent": intent,
                "category_boost": category_boost,
                "subsection_boost": subsection_boost,
                "final_score": final_score
            })

    results.sort(
        key=lambda x: x["final_score"],
        reverse=True
    )

    return results[:top_k]