import requests


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2"

FALLBACK_ANSWER = (
    "I couldn't find the answer in the provided document."
)


def generate_response(
    query: str,
    context: str
) -> str:
    """
    Generate a grounded answer using the local Ollama LLM.
    """

    if not query.strip():
        raise ValueError("Question cannot be empty.")

    if not context.strip():
        return FALLBACK_ANSWER

    prompt = f"""
You answer questions using ONLY the document context below.

If the answer is present in the context, give the answer directly.

If the answer is not present, respond exactly:
{FALLBACK_ANSWER}

For category questions, use the matching section.

For example:
- certifications → CERTIFICATIONS DONE
- education → EDUCATIONAL QUALIFICATIONS
- projects → PROJECTS DONE
- internships → INTERNSHIPS DONE
- programming languages → Programming Languages
- spoken languages → LANGUAGES KNOWN

For a certification question, return ALL certification entries
listed under CERTIFICATIONS DONE.

For a project-list question, return ONLY the project titles/names
listed under PROJECTS DONE.

Do NOT return technologies such as HTML, CSS, JavaScript, PHP,
MySQL, Python, Flask, PostgreSQL, or other tools as project names.

If the PROJECTS DONE section contains technologies before the first
"Title:" entry, ignore those technologies and start with the first
project title.

For questions about a specific project, answer using the relevant
details explicitly provided for that project, such as:

- technologies
- tools
- aim
- technical functionalities
- duration
- team size

Do NOT return the project titles as the answer when the user is
asking about a specific project's technologies, aim, or other details.

DOCUMENT CONTEXT:
-----------------
{context}
-----------------

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
                "stream": False
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
        raise RuntimeError(
            "Could not connect to Ollama. "
            "Make sure Ollama is running."
        )

    except requests.exceptions.Timeout:
        raise RuntimeError(
            "Ollama took too long to generate a response."
        )

    except requests.exceptions.RequestException as error:
        raise RuntimeError(
            f"Ollama request failed: {error}"
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
5. Never transform an ordinary worksheet into a résumé,
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
        raise RuntimeError(
            "Could not connect to Ollama. "
            "Make sure Ollama is running."
        )

    except requests.exceptions.Timeout:
        raise RuntimeError(
            "Ollama took too long to generate the summary."
        )

    except requests.exceptions.RequestException as error:
        raise RuntimeError(
            f"Ollama request failed: {error}"
        )