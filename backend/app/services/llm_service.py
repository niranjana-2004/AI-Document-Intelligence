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

CATEGORY RULES:

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

PROGRAMMING LANGUAGE RULE:

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

Do NOT add HTML, CSS, JavaScript, PHP, Flask, Bootstrap,
SQL, MySQL, PostgreSQL, Power BI, or other technologies unless
they are explicitly listed under Programming Languages.

SPOKEN/HUMAN LANGUAGE RULE:

When the question explicitly asks for:

- spoken languages
- human languages
- languages known
- what languages does the person know

and the document contains a section such as:

LANGUAGES KNOWN
English
Malayalam
Hindi

return ONLY:

English, Malayalam, Hindi

Do NOT include programming languages or technical technologies
in the spoken/human language answer.

WEB TECHNOLOGY RULE:

When the question asks for:

- web technologies
- web technologies/frameworks
- web frameworks
- web development technologies

return ONLY the items explicitly listed under the document's
"Web & Frameworks" or equivalent section.

For example:

Web & Frameworks:
HTML, CSS, JavaScript, Bootstrap, Flask, PHP

Answer:

HTML, CSS, JavaScript, Bootstrap, Flask, PHP

Do NOT add programming languages, databases, tools, or IDEs.

DATABASE RULE:

When the question asks for databases or database technologies,
return ONLY the items explicitly listed under the document's
database section.

For example:

Database Management:
MySQL, PostgreSQL

Answer:

MySQL, PostgreSQL

Do NOT add programming languages, web technologies, tools,
or frameworks.

PROJECT RULE:

When the question asks about projects, return information about
the projects explicitly present in the PROJECTS section.

Do NOT answer a project question with only a list of technologies
used in a project.

If the project section contains project titles, aims,
technologies, duration, team size, or functionalities, use those
details to describe the projects.

Do NOT classify projects as internships, certifications,
workshops, or extracurricular activities.

CERTIFICATION RULE:

When the question asks for certifications, return ONLY items
explicitly present in the CERTIFICATIONS section.

Do NOT include projects, workshops, internships, education,
or technical skills as certifications.

INTERNSHIP RULE:

When the question asks about internships or internship experience,
return ONLY information explicitly present in the INTERNSHIPS
section.

Do NOT treat projects as internships.

EDUCATION RULE:

When the question asks about qualifications, education, degrees,
academic background, or educational qualifications, use the
EDUCATIONAL QUALIFICATIONS section.

Do NOT replace education with certifications, projects,
internships, or technical skills.

SKILLS RULE:

If the question asks specifically for "interpersonal skills",
return ONLY items from the INTERPERSONAL SKILLS section.

If the question asks specifically for "technical skills",
return information from the TECHNICAL SKILLS section while
preserving its categories.

If the question asks generally "What skills does the person have?",
include explicitly listed skills from relevant skill sections,
but do NOT incorrectly classify spoken languages as programming
languages or projects as skills.

GENERAL CATEGORY RULE:

Always determine the requested category from the user's question
before selecting information from DOCUMENT CONTEXT.

Do NOT combine information from different categories merely because
the information appears in the same document or retrieved chunk.

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

AMBIGUOUS LANGUAGE QUESTIONS:

- If the user's question asks generally about "languages" or "what languages
  does the person know" without explicitly saying "programming languages",
  treat the "LANGUAGES KNOWN" section as the intended category when that
  section is present in DOCUMENT CONTEXT.

- For example, if DOCUMENT CONTEXT contains:

  LANGUAGES KNOWN
  English
  Malayalam
  Hindi

  and also contains:

  Programming Languages: C, Java, Python, R

  and the user asks:

  "What languages does Niranjana know?"

  answer:

  "English, Malayalam, Hindi"

- Do NOT return programming languages for an ambiguous "languages" question
  when a "LANGUAGES KNOWN" section is explicitly present.

- Only return programming languages when the user explicitly asks for
  programming languages, coding languages, technical languages, or similar
  wording.

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

- Include ALL items from the requested category that are explicitly
  present in DOCUMENT CONTEXT.

- Never return only the first item when multiple relevant items are
  explicitly present.

- Scan the entire relevant section before producing the answer.

- If the requested section contains multiple entries, include every
  entry that belongs to that category.

- Do not stop because one or two items have already answered the
  question.

- Preserve the original wording, names, dates, CGPAs, percentages,
  durations, and organizations whenever possible.

- Do not omit an item merely because it appears later in the same
  chunk.

- If multiple related entries occur in the same section, combine
  them into one complete answer.
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

QUALIFICATIONS RULE:

When the question asks about:

- qualifications
- qualification
- educational qualifications
- academic qualifications
- education
- educational background
- academic background
- degrees

use the EDUCATIONAL QUALIFICATIONS section.

If DOCUMENT CONTEXT contains an EDUCATIONAL QUALIFICATIONS
section, include ALL educational entries explicitly present
in that section.

Do NOT stop after the first degree or the most recent degree.

For example, if the section contains:

Master of Computer Applications in AI and Data Science
CGPA : 9.23

Bachelor of Computer Applications in Data Science
CGPA : 8.7

Higher Secondary Education
Percentage : 79.4%

Secondary School Education
Percentage : 93%

the answer must include all four qualifications and their
associated academic values.

Do NOT omit Higher Secondary Education or Secondary School
Education merely because they are school-level qualifications.

Preserve the exact CGPA and percentage values from the document.

Do NOT calculate, convert, round, or modify these values.

AMBIGUOUS LANGUAGE QUESTIONS:

- If the user asks "What languages does [person] know?"
  without explicitly mentioning "programming", interpret
  "languages" as spoken/human languages.

- For an ambiguous "languages" question, use the
  "LANGUAGES KNOWN" section.

- Do NOT use the "Programming Languages" section for an ambiguous
  "languages" question.

- If the user explicitly asks for "programming languages", use only
  the "Programming Languages" section.

- If the user explicitly asks for "spoken languages", "human
  languages", or similar wording, use only the "LANGUAGES KNOWN"
  section.

- For example, if the document contains:

  LANGUAGES KNOWN
  English
  Malayalam
  Hindi

  and:

  Programming Languages: C, Java, Python, R

  then:

  "What languages does Niranjana know?"

  MUST be answered:

  "English, Malayalam, Hindi"

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