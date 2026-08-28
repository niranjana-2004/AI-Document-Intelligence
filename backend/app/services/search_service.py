from app.services.embedding_services import generate_embedding
from app.services.similarity_service import cosine_similarity
from app.models.document_chunk import DocumentChunk
import re


SIMILARITY_THRESHOLD = 0.20
FINAL_SCORE_THRESHOLD = 0.20

SEMANTIC_WEIGHT = 0.70
KEYWORD_WEIGHT = 0.30


# Common abbreviations and their full forms
QUERY_EXPANSIONS = {
    "bca": "Bachelor of Computer Applications",
    "mca": "Master of Computer Applications",
}


# Query categories and the section keywords
# that should receive a ranking boost.
CATEGORY_KEYWORDS = {
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
        "master"
    ],

    "projects": [
        "project",
        "projects"
    ],

    "internship": [
        "internship",
        "intern",
        "internships"
    ],

    "workshops": [
        "workshop",
        "workshops",
        "bootcamp"
    ],

    "certifications": [
        "certification",
        "certifications",
        "certificate",
        "certificates",
        "course",
        "courses"
    ],

    "awards": [
        "award",
        "awards",
        "achievement",
        "achievements"
    ]
}


# Section headings that identify the actual document category.
SECTION_MARKERS = {
    "education": [
        "educational qualifications",
        "higher secondary education",
        "secondary school education",
        "master of computer applications",
        "bachelor of computer applications",
    ],

    "projects": [
        "projects done",
        "title:",
        "aim:",
        "technical functionalities:",
        "tools and technologies used:",
    ],

    "internship": [
        "internships done",
        "organization name:",
        "data science intern",
        "responsibilities:",
    ],

    "workshops": [
        "workshops done",
        "3 days session",
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


def expand_query(query: str) -> str:
    """
    Expand common abbreviations in the user's query
    so that semantic search can match their full forms.
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


def detect_query_category(query: str) -> str | None:
    """
    Detect the primary information category being requested.

    The function prioritizes the category that appears to be
    the actual subject of the question rather than contextual
    phrases such as "during their internship".
    """

    query_lower = query.lower()

    # Strong explicit category phrases.
    # These should take priority over contextual words.
    explicit_categories = {
        "certifications": [
            "certification",
            "certifications",
            "certificate",
            "certificates"
        ],

        "projects": [
            "project",
            "projects"
        ],

        "workshops": [
            "workshop",
            "workshops",
            "bootcamp"
        ],

        "awards": [
            "award",
            "awards",
            "achievement",
            "achievements"
        ],

        "education": [
            "education",
            "qualification",
            "qualifications",
            "degree",
            "cgpa",
            "percentage",
            "bca",
            "mca",
            "bachelor",
            "master"
        ],

        "internship": [
            "internship",
            "internships",
            "intern"
        ]
    }

    # Check explicit requested categories first.
    # This prevents phrases such as "during their internship"
    # from incorrectly overriding certifications/projects/etc.
    for category in [
        "certifications",
        "projects",
        "workshops",
        "awards",
        "education"
    ]:

        for keyword in explicit_categories[category]:

            if re.search(
                rf"\b{re.escape(keyword)}\b",
                query_lower
            ):
                return category

    # Internship is checked after the other categories because
    # it is frequently used as contextual information.
    for keyword in explicit_categories["internship"]:

        if re.search(
            rf"\b{re.escape(keyword)}\b",
            query_lower
        ):
            return "internship"

    return None

def detect_query_context(query: str) -> str | None:
    """
    Detect contextual constraints in the user's question.

    For example:
        "projects during their internship"
        -> internship

    The context is different from the primary category.
    """

    query_lower = query.lower()

    internship_phrases = [
        "during their internship",
        "during the internship",
        "in their internship",
        "in the internship",
        "while doing their internship",
        "while on their internship",
        "as part of their internship"
    ]

    for phrase in internship_phrases:
        if phrase in query_lower:
            return "internship"

    return None


def calculate_keyword_score(query: str, content: str) -> float:
    """
    Calculate keyword/concept overlap between the query
    and document chunk.

    Known abbreviations such as BCA/MCA are treated as
    equivalent to their full forms.
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

    # Check abbreviation/full-form equivalence
    for abbreviation, full_form in QUERY_EXPANSIONS.items():

        if abbreviation in query_words:

            full_form_words = set(
                re.findall(
                    r"\b[a-zA-Z0-9]+\b",
                    full_form.lower()
                )
            )

            if full_form_words.issubset(
                content_words
            ):
                matched_words.add(
                    abbreviation
                )

    return len(matched_words) / len(query_words)


def calculate_category_boost(
    category: str | None,
    content: str
) -> float:
    """
    Give a ranking boost when a chunk contains
    strong evidence that it belongs to the requested category.
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
        return 0.30

    return 0.20


def semantic_search(
    query: str,
    db,
    document_id: int | None = None,
    top_k: int = 5
):
    """
    Perform hybrid semantic + keyword + category search.
    """

    # Expand abbreviations before generating the embedding.
    expanded_query = expand_query(query)

    query_embedding = generate_embedding(
        expanded_query
    )

    # Detect what type of information the user is asking for.
    category = detect_query_category(query)

    # Detect contextual constraints such as
    # "during their internship".
    query_context = detect_query_context(query)

    query_db = db.query(DocumentChunk)

    if document_id is not None:

        query_db = query_db.filter(
            DocumentChunk.document_id == document_id
        )

    chunks = query_db.all()

    results = []

    for chunk in chunks:

        if not chunk.embedding:
            continue

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

        # Ignore chunks only when they have no meaningful
        # semantic, keyword, or category relevance.
        if (
            similarity < SIMILARITY_THRESHOLD
            and keyword_score == 0
            and category_boost == 0
        ):
            continue

        final_score = (
            SEMANTIC_WEIGHT * similarity
            + KEYWORD_WEIGHT * keyword_score
            + category_boost
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
                "category_boost": category_boost,
                "final_score": final_score
            })

    results.sort(
        key=lambda x: x["final_score"],
        reverse=True
    )

    return results[:top_k]