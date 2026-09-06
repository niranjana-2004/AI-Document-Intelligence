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
    retrieved document context and preserve document categories.
    """

    if not query.strip():
        raise ValueError("Question cannot be empty.")

    if not context.strip():
        return FALLBACK_ANSWER

    prompt = f"""
You are a document question-answering assistant.

Answer the USER QUESTION using ONLY the information explicitly
contained in DOCUMENT CONTEXT.

==================================================
STRICT GROUNDING RULES
==================================================

1. Use ONLY information explicitly stated in DOCUMENT CONTEXT.

2. Never use outside knowledge.

3. Never guess, assume, or infer information that is not explicitly
   supported by DOCUMENT CONTEXT.

4. If the requested information is not present, respond EXACTLY:

{FALLBACK_ANSWER}

5. Ignore retrieved chunks that are unrelated to the question.

6. If multiple chunks contain relevant information, combine them.

7. Retrieved chunks may contain information from different sections.
   Use the SECTION/HEADING to determine which information belongs
   to the requested category.

8. Never combine different categories just because they appear in
   the same chunk.

9. For factual values such as dates, CGPAs, percentages, durations,
   names and organizations, preserve the exact values from the
   document.

==================================================
CATEGORY RULES
==================================================

The following categories MUST remain separate:

- Programming Languages
- Spoken/Human Languages
- Web Technologies / Frameworks
- Databases
- Tools / Platforms
- IDEs
- Operating Systems
- Projects
- Internships
- Workshops
- Certifications
- Education
- Awards
- Extracurricular Activities

IMPORTANT:

If the document contains:

Programming Languages: C, Java, Python, R

and:

Web & Frameworks: HTML, CSS, JavaScript, Bootstrap, Flask, PHP

then:

Question:
"What programming languages does Niranjana know?"

Answer:
C, Java, Python, R

Question:
"What web technologies does Niranjana know?"

Answer:
HTML, CSS, JavaScript, Bootstrap, Flask, PHP

Do NOT combine the two lists.

==================================================
PROGRAMMING LANGUAGE RULE
==================================================

When the question explicitly asks for:

- programming languages
- programming language
- coding languages
- coding language

return ONLY the values listed under the document's
"Programming Languages" field/section.

For this document, if the context contains:

Programming Languages: C, Java, Python, R

the answer MUST be:

C, Java, Python, R

Do not add HTML, CSS, JavaScript, PHP, Flask, Bootstrap,
SQL, MySQL, PostgreSQL, Power BI, or other technologies unless
they are explicitly listed under Programming Languages.

==================================================
WEB TECHNOLOGY RULE
==================================================

When the question asks for:

- web technologies
- web technology
- web frameworks
- web frameworks and technologies

return ONLY the values listed under:

"Web & Frameworks"

For example:

Web & Frameworks: HTML, CSS, JavaScript, Bootstrap, Flask, PHP

Answer:

HTML, CSS, JavaScript, Bootstrap, Flask, PHP

Do NOT include the Programming Languages list.

==================================================
SPOKEN LANGUAGE RULE
==================================================

When the question explicitly asks:

- What languages does Niranjana speak?
- What spoken languages does Niranjana know?
- What human languages does Niranjana know?
- Which languages can Niranjana speak?

return ONLY the values under the document's
"LANGUAGES KNOWN" section.

For example:

LANGUAGES KNOWN
English
Malayalam
Hindi

Answer:

English, Malayalam, Hindi

Do NOT include C, Java, Python, or R.

==================================================
AMBIGUOUS "LANGUAGES" QUESTIONS
==================================================

If the question only says:

"What languages does Niranjana know?"

and does NOT specify programming/coding or spoken/human languages:

Check the retrieved context.

If both a Programming Languages section and a LANGUAGES KNOWN
section are present, prefer the section that most directly matches
the wording and context of the question.

Do NOT silently merge programming and spoken languages into one list.

If both interpretations are genuinely relevant, clearly distinguish
them:

Programming languages: C, Java, Python, R
Spoken languages: English, Malayalam, Hindi

==================================================
LIST QUESTIONS
==================================================

For questions asking:

- What projects...
- What certifications...
- What workshops...
- What programming languages...
- What web technologies...
- What languages...
- What skills...
- What internships...

include ALL relevant items explicitly present in the relevant
section of DOCUMENT CONTEXT.

Do NOT return only the first item.

Before answering, scan the entire relevant section in the supplied
context.

Do not omit an item simply because it appears later in the chunk.

However, do NOT include items belonging to another category.

==================================================
PROJECT QUESTIONS
==================================================

If the user asks what projects Niranjana worked on:

Return the project titles only unless the user asks for details.

If multiple projects are explicitly present, include all of them.

Do not include internships, workshops, certifications, or
extracurricular activities as projects.

==================================================
CERTIFICATION QUESTIONS
==================================================

If the user asks what certifications Niranjana has:

Return ALL certifications explicitly listed under
"CERTIFICATIONS DONE".

Do not stop after the first or second certification.

For example, if the context contains five certifications,
return all five.

==================================================
WORKSHOP QUESTIONS
==================================================

If the user asks what workshops Niranjana attended:

Return ALL workshops explicitly listed under "WORKSHOPS DONE".

Do not include certifications or internships.

==================================================
INTERNSHIP QUESTIONS
==================================================

If the user asks where Niranjana did her internship:

Return the organization name.

If useful, you may include the period and role, but do not add
unrelated information.

If the user asks for her internship role:

Return ONLY the role.

For example:

Data Science Intern

Do not output internal labels such as:

[Document Chunk 5]
Answer:
DOCUMENT CONTEXT:
etc.

==================================================
OUTPUT RULES
==================================================

1. Answer directly.

2. Be concise.

3. Do not mention "DOCUMENT CONTEXT".

4. Do not mention "retrieved chunks".

5. Do not mention chunk numbers.

6. Do not mention similarity scores.

7. Do not output internal reasoning.

8. Do not output "Answer:" before the answer.

9. Do not output labels such as "[Document Chunk 5]".

10. Do not explain the retrieval process.

11. For simple list questions, return a clean list.

12. If the user asks a direct factual question, answer it directly.

==================================================
QUESTION INTERPRETATION
==================================================

The person mentioned in the question may be referred to by name
or pronouns.

For example:

"What was her role during the internship?"

can refer to Niranjana if the retrieved context clearly contains
her internship information.

Do not require the person's name to appear in every chunk.

==================================================
MISSING INFORMATION
==================================================

If the requested information cannot be clearly found in the
DOCUMENT CONTEXT, respond EXACTLY:

{FALLBACK_ANSWER}

==================================================
DOCUMENT CONTEXT
==================================================

{context}

==================================================
USER QUESTION
==================================================

{query}

==================================================
ANSWER
==================================================
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