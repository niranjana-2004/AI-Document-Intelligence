import re
import requests


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2"

FALLBACK_ANSWER = (
    "The provided documents do not contain sufficient information to answer this question."
)


class LLMServiceError(RuntimeError):
    """Base exception for LLM service failures."""
    pass


class LLMConnectionError(LLMServiceError):
    """Raised when the LLM service is unreachable."""
    pass


class LLMTimeoutError(LLMServiceError):
    """Raised when the LLM service request times out."""
    pass


def format_conversation_history(conversation_history: list | None) -> str:
    """Format validated recent conversation turns for LLM prompt context."""
    if not conversation_history:
        return ""

    formatted_turns = []
    for message in conversation_history:
        role = message.get("role", "") if isinstance(message, dict) else getattr(message, "role", "")
        content = message.get("content", "") if isinstance(message, dict) else getattr(message, "content", "")
        speaker = "User" if role == "user" else "Assistant"
        formatted_turns.append(f"{speaker}: {content.strip()}")

    return "\n".join(formatted_turns).strip()


def generate_response(
    query: str,
    context: str,
    conversation_history: list | None = None
) -> str:
    """
    Generate a grounded, synthesized answer with inline source citations
    using the local Ollama LLM.
    """

    if not query.strip():
        raise ValueError("Question cannot be empty.")

    if not context.strip():
        return FALLBACK_ANSWER

    history_text = format_conversation_history(conversation_history)
    history_section = (
        f"CONVERSATION HISTORY:\n--------\n{history_text}\n--------\n\n"
        if history_text
        else ""
    )

    prompt = f"""You are Cognidocs AI, an intelligent document analysis assistant.
Answer the user's question directly, concisely, and factually using ONLY the provided document sources.

STRICT GUIDELINES:
1. Grounded synthesis: Synthesize a clear, direct answer in your own words based exclusively on the provided sources. Do not reproduce entire source chunks verbatim.
2. Inline citations: Cite the source number in square brackets, such as [1] or [2], immediately after each statement, fact, or claim derived from that source (e.g., "The system employs AES-256 encryption [1] and SHA-256 hashing [2].").
3. Source numbering rule: Each source is identified by a "[Source N | ...]" header label. You must ONLY cite the assigned header number N (e.g., [1], [2], [3], etc.).
   DO NOT copy internal reference markers that happen to appear inside the document text (such as academic bibliography numbers like [5], [16], [28]). Always cite the assigned [Source N] number that contains the evidence.
4. Valid citations only: Only reference source numbers that actually appear in the [Source N] headers below. Never cite non-existent source numbers.
5. Strict factual grounding: Do not use outside knowledge, extrapolate, speculate, or fabricate any facts, quotes, page numbers, or filenames.
6. Inadequate information: If the provided sources do not contain sufficient information to answer the question, respond exactly with:
"{FALLBACK_ANSWER}"
Do not guess or provide unsupported speculation.
7. Formatting: Use concise paragraphs or a clean list if multiple items are requested. Keep the response professional, natural, and directly focused on the inquiry.
8. Conversational grounding: Conversation history is provided solely to understand conversational context and resolve follow-up references. Conversation history is NOT evidence. All factual claims must be strictly grounded in the SOURCES below and must cite only source indices ([1], [2], etc.) from the current SOURCES.

{history_section}SOURCES:
--------
{context}
--------

USER QUESTION:
{query}

ANSWER:
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2
                }
            },
            timeout=120
        )

        response.raise_for_status()

        data = response.json()

        answer = data.get("response", "").strip()

        if not answer:
            return FALLBACK_ANSWER

        return answer

    except requests.exceptions.ConnectionError:
        raise LLMConnectionError(
            "The AI generation service is currently unreachable. "
            "Please ensure Ollama is running."
        )

    except requests.exceptions.Timeout:
        raise LLMTimeoutError(
            "The AI model took too long to generate a response. "
            "Please try again or simplify your query."
        )

    except requests.exceptions.RequestException:
        raise LLMServiceError(
            "An error occurred while communicating with the AI generation service."
        )


MAX_SUMMARY_INPUT_CHARS = 12000

SUMMARY_FORMAT_INSTRUCTIONS = {
    "numbered": "Present the summary as a structured, numbered list of main points.",
    "paragraphs": "Present the summary as cohesive, well-organized paragraphs.",
    "bullets": "Present the summary as clear, structured bullet points.",
    "headings": "Present the summary organized under relevant, content-specific headings and subheadings.",
}

SUMMARY_LENGTH_INSTRUCTIONS = {
    "brief": "Keep the summary concise and high-level (approximately 1-2 paragraphs or 3-5 key points), highlighting only essential takeaways.",
    "detailed": "Provide a comprehensive, detailed summary covering important concepts, context, findings, and nuances.",
}


def prepare_summary_input(text: str, max_chars: int = MAX_SUMMARY_INPUT_CHARS) -> tuple[str, bool]:
    """
    Bound document text for LLM summarization without exceeding context budgets.
    For documents exceeding max_chars, samples opening, middle, and concluding sections.
    """
    text_clean = text.strip()
    total_len = len(text_clean)
    if total_len <= max_chars:
        return text_clean, False

    head_budget = int(max_chars * 0.40)
    mid_budget = int(max_chars * 0.25)
    tail_budget = max_chars - head_budget - mid_budget

    # 1. Opening section
    head_cut = text_clean[:head_budget]
    last_nl = head_cut.rfind("\n")
    if last_nl > head_budget - 400:
        head_text = head_cut[:last_nl].strip()
    else:
        head_text = head_cut.strip()

    # 2. Middle section (centered around midpoint)
    mid_center = total_len // 2
    mid_start = max(0, mid_center - (mid_budget // 2))
    mid_end = min(total_len, mid_start + mid_budget)
    mid_slice = text_clean[mid_start:mid_end]
    first_nl = mid_slice.find("\n")
    last_nl = mid_slice.rfind("\n")
    if first_nl != -1 and last_nl != -1 and last_nl > first_nl:
        mid_text = mid_slice[first_nl:last_nl].strip()
    else:
        mid_text = mid_slice.strip()

    # 3. Concluding section
    tail_start = max(0, total_len - tail_budget)
    tail_slice = text_clean[tail_start:]
    first_nl = tail_slice.find("\n")
    if first_nl != -1 and first_nl < 400:
        tail_text = tail_slice[first_nl:].strip()
    else:
        tail_text = tail_slice.strip()

    sampled_text = (
        f"--- [EXCERPT 1: OPENING / OVERVIEW] ---\n{head_text}\n\n"
        f"--- [EXCERPT 2: CENTRAL CONTENT / METHODOLOGY] ---\n{mid_text}\n\n"
        f"--- [EXCERPT 3: CONCLUDING CONTENT / RESULTS] ---\n{tail_text}"
    )
    return sampled_text, True


def generate_summary(
    text: str,
    summary_format: str = "numbered",
    summary_length: str = "detailed"
) -> str:
    """
    Generate a concise and factually faithful summary
    of the document using the local Ollama LLM.
    """
    if not text or not text.strip():
        return "I couldn't generate a summary because the document is empty."

    format_key = summary_format.lower() if summary_format else "numbered"
    length_key = summary_length.lower() if summary_length else "detailed"

    format_instruction = SUMMARY_FORMAT_INSTRUCTIONS.get(
        format_key,
        SUMMARY_FORMAT_INSTRUCTIONS["numbered"]
    )
    length_instruction = SUMMARY_LENGTH_INSTRUCTIONS.get(
        length_key,
        SUMMARY_LENGTH_INSTRUCTIONS["detailed"]
    )

    bounded_text, is_sampled = prepare_summary_input(text)

    if is_sampled:
        source_header = (
            f"SOURCE DOCUMENT EXCERPTS (Sampled from the opening, middle, and concluding sections "
            f"of a {len(text.strip()):,} character document):\n"
            f"Base your summary strictly on these provided excerpts without assuming or inventing details from unsupplied sections."
        )
    else:
        source_header = "SOURCE DOCUMENT:"

    prompt = f"""You are Cognidocs AI, an expert document intelligence assistant.
Analyze the provided document text and produce an accurate, objective, and well-structured summary.

CORE GUIDELINES:
1. Factual grounding: Base the summary strictly on the information explicitly present in the source text. Never invent facts, figures, skills, findings, or conclusions.
2. Adaptive content analysis:
   - For resumes or curriculum vitae: summarize the candidate's actual qualifications, technical and professional skills, education, and notable experience.
   - For research papers or academic studies: summarize the research objectives, methodologies, key findings, and conclusions.
   - For technical reports or specifications: summarize the project scope, system components or architecture, implementation details, and outcomes.
   - For general documents or articles: summarize the primary topics, core arguments, and takeaways.
3. Strict omission: If a detail, section, or topic is not present in the document, completely omit it. Never include placeholder headings or disclaimers such as "Not listed", "Not specified", "No information provided", or "None mentioned".
4. Formatting: {format_instruction}
5. Depth: {length_instruction}
6. Tone: Professional, objective, and informative. Begin directly with the summary content without conversational preambles like "Here is a summary".

{source_header}
----------------
{bounded_text}
----------------

SUMMARY:
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3
                }
            },
            timeout=300
        )

        response.raise_for_status()
        data = response.json()
        summary = data.get("response", "").strip()

        if not summary:
            return "I couldn't generate a summary for this document."

        return summary

    except requests.exceptions.ConnectionError:
        raise LLMConnectionError(
            "The AI generation service is currently unreachable. "
            "Please ensure Ollama is running."
        )

    except requests.exceptions.Timeout:
        raise LLMTimeoutError(
            "The AI model took too long to generate the summary."
        )

    except requests.exceptions.RequestException:
        raise LLMServiceError(
            "An error occurred while communicating with the AI generation service."
        )



def generate_suggested_questions_llm(
    summary_context: str,
    max_questions: int = 4
) -> list[str]:
    """
    Generate concise, document-grounded suggested questions using the local Ollama LLM.
    """
    if not summary_context or not summary_context.strip():
        return []

    prompt = f"""You are Cognidocs AI, an intelligent document analysis assistant.
Based on the following document context, generate {max_questions} concise, high-value questions that a user would likely ask about this content.

STRICT RULES:
1. Grounding: Every question must be strictly relevant to the document topics, facts, or findings provided below.
2. Output format: Output ONLY the questions, exactly one question per line.
3. No numbering, no bullet points, no quotation marks, no conversational prefixes, and no explanations.
4. Each question must be complete, specific, and end with a question mark '?'.
5. Keep each question natural, direct, and under 15 words.

DOCUMENT CONTEXT:
--------
{summary_context.strip()}
--------

QUESTIONS:
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3
                }
            },
            timeout=25
        )

        response.raise_for_status()
        data = response.json()
        raw_output = data.get("response", "").strip()

        if not raw_output:
            return []

        questions: list[str] = []
        for line in raw_output.splitlines():
            cleaned = line.strip()
            if not cleaned:
                continue
            # Strip markdown bullets or numbered prefixes like "1. ", "- ", "* "
            cleaned = re.sub(r"^(?:\d+[\.\)]|[-*•])\s+", "", cleaned).strip()
            # Strip quotes
            cleaned = cleaned.strip('"\'')
            if not cleaned:
                continue
            # Ensure it ends with ?
            if not cleaned.endswith("?"):
                cleaned += "?"
            # Ignore conversational filler lines like "Here are 4 questions:"
            if cleaned.lower().startswith(("here are", "sure,", "certainly", "based on")):
                continue
            if len(cleaned.split()) >= 3 and cleaned not in questions:
                questions.append(cleaned)

        return questions[:max_questions]

    except requests.exceptions.ConnectionError:
        raise LLMConnectionError(
            "The AI generation service is currently unreachable. "
            "Please ensure Ollama is running."
        )
    except requests.exceptions.Timeout:
        raise LLMTimeoutError(
            "The AI model took too long to generate suggested questions."
        )
    except requests.exceptions.RequestException:
        raise LLMServiceError(
            "An error occurred while communicating with the AI generation service."
        )
