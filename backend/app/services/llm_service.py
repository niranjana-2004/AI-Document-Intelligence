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

def generate_summary(text: str) -> str:
    """
    Generate a concise and factually faithful summary
    of the document using the local Ollama LLM.
    """

    if not text.strip():
        return "I couldn't generate a summary because the document is empty."

    prompt = f"""
You are a document summarization assistant.

Your task is to summarize the document provided below.

STRICT SOURCE RULES:

1. Use ONLY information explicitly present in the document.

2. Do NOT use general knowledge.

3. Do NOT invent, assume, estimate, or infer information.

4. Do NOT change, reinterpret, or reclassify information.

5. Preserve the meaning and category of information exactly as it
   appears in the document.

SECTION ACCURACY RULES:

6. Treat document sections as authoritative.

7. If the document contains a section called "Programming Languages",
   report ONLY the languages listed in that section as programming
   languages.

8. Do NOT move technologies, tools, frameworks, databases, or other
   skills into the Programming Languages category.

9. Treat the following categories separately:

   - Programming Languages
   - Web Technologies / Frameworks
   - Databases
   - Tools / Platforms
   - IDEs
   - Operating Systems
   - Spoken / Human Languages
   - Projects
   - Internships
   - Workshops
   - Certifications
   - Awards
   - Education

10. Do not move an item from one category to another.

FACTUAL ACCURACY:

11. Preserve exact numerical values.

12. Preserve exact CGPAs and percentages.

13. Preserve names of organizations, institutions, projects,
    certifications, and internship roles.

14. Preserve dates and durations when explicitly stated.

15. Do not calculate, round, convert, or modify numerical information.

SUMMARY STRUCTURE:

Organize the summary using only sections that are actually present
in the document.

Use a structure such as:

- Overview
- Education
- Technical Skills
- Projects
- Internships
- Workshops
- Certifications
- Achievements
- Other relevant information

Do NOT create a section if the document does not contain relevant
information for it.

IMPORTANT:

Before producing the summary, carefully distinguish information based
on the section where it appears.

For example, if the document contains:

Programming Languages: C, Java, Python, R

and elsewhere says:

Proficient in Python, SQL, and Power BI

the Programming Languages section MUST remain:

C, Java, Python, R

Do not replace it with Python, SQL, Power BI.

Keep the summary concise but informative.

DOCUMENT:
-----------------
{text}
-----------------

SUMMARY:
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