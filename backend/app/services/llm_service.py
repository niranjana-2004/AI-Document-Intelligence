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
    Generate a concise summary of the document using the local Ollama LLM.
    """

    prompt = f"""
You are a document summarization assistant.

Your task is to summarize the provided document.

IMPORTANT RULES:

1. Use ONLY information explicitly present in the document.
2. Do NOT use your general knowledge.
3. Do NOT invent, assume, or infer information.
4. Include the most important information from the document.
5. Preserve important factual details such as names, organizations,
   qualifications, CGPAs, percentages, dates, project names, and roles.
6. Do not confuse projects with internships, certifications, or workshops.
7. Do not confuse programming languages with spoken languages.
8. Organize the summary clearly.
9. Keep the summary concise but informative.
10. If the document contains multiple sections, summarize the important
    information from each relevant section.

DOCUMENT:

{text}

SUMMARY:
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False
        }
    )

    response.raise_for_status()

    data = response.json()

    return data["response"].strip()