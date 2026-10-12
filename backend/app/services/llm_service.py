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


def generate_summary(
    text: str,
    summary_format: str = "numbered",
    summary_length: str = "detailed"
) -> str:
    """
    Generate a concise and factually faithful summary
    of the document using the local Ollama LLM.
    """

    if not text.strip():
        return "I couldn't generate a summary because the document is empty."
   
    prompt = f"""
You are a professional document summarization assistant.

Your task is to produce an accurate, detailed, natural-language
summary of the source document.

CONSISTENT WRITING STYLE:
Every summary must follow the same writing style:
- Use connected, well-organized paragraphs.
- Begin by identifying the document's actual subject and purpose.
- Explain the important content in a logical sequence.
- Describe relevant components, concepts, methods, processes,
  examples, findings, results, or conclusions when present.
- Preserve specific names, technical terms, numbers, measurements,
  commands, and other important details.
- End with a concise overall explanation of what the document
  covers or accomplishes, when supported by its content.
- Write like an informative explanation of the document, not
  like a template filled with predefined categories.
- Use the same natural, explanatory style for every document,
  whether it is a research paper, project report, study material,
  aptitude worksheet, technical manual, or another document.

STRICT SOURCE RULES:
1. Use only information supported by the source document.
2. Never invent topics, questions, skills, examples, results,
   findings, or conclusions.
3. Do not add information from general knowledge.
4. Do not assume the document contains content that was not
   extracted from the source.
5. Preserve the meaning and context of the original information.
6. Include important details in proportion to their importance.
7. If information is missing or unclear, do not guess.

STRICT OUTPUT RULES:
1. Write the summary primarily as paragraphs, using multiple
   paragraphs when needed.
2. Do not use predefined headings such as Overview, Education,
   Technical Skills, Projects, Internships, Workshops,
   Certifications, Achievements, or Results automatically.
3. Include a heading only if it genuinely helps explain the
   document's actual content.
4. Never include statements such as "No projects are listed,"
   "No information was provided," or "Not listed" for categories
   unrelated to the document.
5. Never transform an ordinary worksheet into a rAcsumAc,
   project report, research paper, or academic profile.
6. For a question paper or practice worksheet, describe the
   actual questions, exercises, instructions, and topics that
   are present in the extracted text. Do not invent questions
   or topics based on what such worksheets commonly contain.
7. For a technical report or research paper, explain its actual
   purpose, design, components, methodology, results, limitations,
   and conclusions when those details are present.
8. Avoid repetitive conclusions, generic filler, and unnecessary
   disclaimers.
9. Do not begin with "Here is a summary of the document."
10. Do not refer to these instructions in the final summary.

LENGTH:
Produce a sufficiently detailed summary to preserve the document's
important information without reproducing the entire source.
Choose the length according to the amount and complexity of
relevant information in the source.
FORMAT INSTRUCTIONS:
- Summary format: {summary_format}
- Summary length: {summary_length}

Use the selected format:
- numbered: organize the main points as a numbered list.
- paragraphs: write connected paragraphs.
- bullets: use bullet points.
- headings: use relevant headings and subheadings.

Use the selected length:
- brief: include only the essential information.
- detailed: explain the important details supported by the source.

Never invent information or introduce unrelated categories.
SOURCE DOCUMENT:
----------------
{text}
----------------

Write the summary now.
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False
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
