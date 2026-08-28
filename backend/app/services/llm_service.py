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

    The LLM is strictly instructed to answer only from the
    retrieved document context.
    """

    if not query.strip():
        raise ValueError("Question cannot be empty.")

    if not context.strip():
        return FALLBACK_ANSWER

    prompt = f"""
You are a document question-answering assistant.

Your job is to answer the user's question using ONLY the information
contained in DOCUMENT CONTEXT.

STRICT GROUNDING RULES:

1. Use ONLY information explicitly stated in DOCUMENT CONTEXT.

2. Do NOT use your general knowledge.

3. Do NOT guess, assume, estimate, or infer information that is not
   explicitly supported by DOCUMENT CONTEXT.

4. If the answer is not present in DOCUMENT CONTEXT, respond exactly:
   "{FALLBACK_ANSWER}"

5. Ignore retrieved chunks that are unrelated to the question.

6. A chunk being retrieved does NOT mean that its information is
   relevant to the question.

7. If multiple chunks are relevant, combine their information carefully.

8. Never combine unrelated information merely because it appears in
   the same document.

9. For numerical values, preserve the exact value stated in the document.
   Do not calculate, round, convert, or modify it unless the user
   explicitly asks for a calculation.

10. Answer the question directly and concisely.

CATEGORY RULES:

- Programming languages are different from human/spoken languages.
- Technical skills are different from programming languages.
- Projects are different from internships.
- Projects are different from certifications.
- Projects are different from workshops.
- Internships are different from projects.
- Education details are different from certifications.
- Awards are different from extracurricular activities.

For example:
If the question asks for programming languages, do NOT include
English, Malayalam, or Hindi just because they appear in the document.

If the question asks for certifications, do NOT include projects,
workshops, or internships.

If the question asks about an internship, do NOT describe a project
unless the document explicitly connects that project to the internship.

LIST QUESTIONS:

- Include only items that belong to the requested category.
- Do not add related but different items.
- If the document explicitly provides a list, preserve the listed items.

FACTUAL QUESTIONS:

- Return the exact information stated in the document whenever possible.
- For CGPA, percentages, dates, durations, names, organizations, and
  other factual values, do not alter the original information.

MISSING INFORMATION:

If the requested information cannot be clearly found in the context,
respond exactly:

"{FALLBACK_ANSWER}"

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

9. If the document says someone is "proficient in Python, SQL, and
   Power BI" in a career summary, do NOT automatically classify SQL
   or Power BI as programming languages.

10. Treat the following categories separately:

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

11. Do not move an item from one category to another.

FACTUAL ACCURACY:

12. Preserve exact numerical values.

13. Preserve exact CGPAs and percentages.

14. Preserve names of organizations, institutions, projects,
    certifications, and internship roles.

15. Preserve dates and durations when they are explicitly stated.

16. Do not calculate, round, convert, or modify numerical information.

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