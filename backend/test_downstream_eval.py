import sys
import os
import json

backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

from app.core.database import SessionLocal
from app.models.document import Document
from app.services.handwriting.subject_service import classify_subject_from_text, auto_detect_and_set_subject
from app.services.handwriting.handwritten_summary_service import generate_handwritten_summary
from app.services.handwriting.handwritten_concept_service import generate_handwritten_concepts
from app.services.handwriting.handwritten_quiz_service import generate_handwritten_quiz
from app.services.handwriting.handwritten_flashcard_service import generate_handwritten_flashcards
from app.services.handwriting.handwritten_chat_service import ask_handwritten_notes
from app.services.handwriting.handwritten_source_service import sync_handwritten_chunks_and_embeddings

def test_downstream():
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == 12).first()
        user_id = doc.user_id

        print(f"--- 1. SUBJECT DETECTION FOR DOC #{doc.id} (User: {user_id}) ---")
        detected_subject = auto_detect_and_set_subject(doc.id, user_id, db)
        print(f"Detected and Persisted Subject: '{detected_subject}'")

        # Sync chunks to ensure vector retrieval works for chat
        sync_handwritten_chunks_and_embeddings(doc.id, db)

        print("\n--- 2. STUDY SUMMARY TEST ---")
        summary_res = generate_handwritten_summary(
            document_id=doc.id,
            user_id=user_id,
            db=db,
            summary_type="detailed"
        )
        print(f"Summary Overview:\n{summary_res.get('overview', '')[:250]}...")
        print(f"Key Takeaways ({len(summary_res.get('key_takeaways', []))}):")
        for kt in summary_res.get('key_takeaways', [])[:3]:
            print(f"  * {kt}")
        print(f"Exam Tips ({len(summary_res.get('exam_tips', []))}):")
        for et in summary_res.get('exam_tips', [])[:2]:
            print(f"  * {et}")

        print("\n--- 3. KEY CONCEPTS EXTRACTION TEST ---")
        concept_data = generate_handwritten_concepts(
            document_id=doc.id,
            user_id=user_id,
            db=db
        )
        concepts = concept_data.get("concepts", [])
        print(f"Total Concepts Extracted: {len(concepts)}")
        for c in concepts[:4]:
            print(f"  - Term: '{c.get('name')}'")
            print(f"    Definition: {c.get('definition', '')[:120]}...")
            print(f"    Page: {c.get('page_number')}")
            print(f"    Excerpt: {c.get('excerpt', '')[:80]}...")

        print("\n--- 4. ADVANCED QUIZ GENERATION TEST ---")
        quiz_res = generate_handwritten_quiz(
            document_id=doc.id,
            user_id=user_id,
            db=db,
            difficulty="mixed",
            question_count=4,
            question_types="all"
        )
        questions = quiz_res.get("questions", [])
        print(f"Total Quiz Questions: {len(questions)}")
        for q in questions:
            print(f"  [{q.get('question_type')} | {q.get('difficulty')}] Q: {q.get('question')}")
            if q.get('options'):
                print(f"     Options: {q.get('options')}")
            print(f"     Explanation: {q.get('explanation', '')[:100]}...")
            print(f"     Ref: {q.get('source_reference')}")

        print("\n--- 5. 3D FLASHCARDS GENERATION TEST ---")
        fc_res = generate_handwritten_flashcards(
            document_id=doc.id,
            user_id=user_id,
            db=db,
            card_count=5
        )
        cards = fc_res.get("flashcards", [])
        print(f"Total Flashcards Generated: {len(cards)}")
        for c in cards[:3]:
            print(f"  [{c.get('card_type')}] Front: {c.get('front')}")
            print(f"     Back: {c.get('back', '')[:100]}...")
            print(f"     Page Ref: {c.get('source_reference')}")

        print("\n--- 6. CHAT WITH NOTES TEST ---")
        test_questions = [
            "What is a TCP SYN Flood attack and how does it exploit the handshake?",
            "What is a TCP RST attack?",
            "Explain how quantum teleportation works."  # Out of domain / unsupported
        ]
        chat_results = []
        for q in test_questions:
            print(f"\nUser Query: '{q}'")
            ans = ask_handwritten_notes(doc.id, q, user_id, db)
            print(f"Answer: {ans.get('answer', '')[:250]}...")
            print(f"Sources Count: {len(ans.get('sources', []))}")
            if ans.get('sources'):
                print(f"First Source: Page {ans['sources'][0].get('page_number')} - '{ans['sources'][0].get('excerpt', '')[:80]}...'")
            chat_results.append({
                "query": q,
                "answer": ans.get("answer"),
                "sources": ans.get("sources")
            })

        with open("downstream_ai_results.json", "w", encoding="utf-8") as f:
            json.dump({
                "subject": detected_subject,
                "summary": summary_res,
                "concepts": concepts,
                "quiz": quiz_res,
                "flashcards": fc_res,
                "chat_evaluations": chat_results
            }, f, indent=2)

        print("\nDownstream AI Grounding Evaluation successfully written to downstream_ai_results.json!")

    finally:
        db.close()

if __name__ == "__main__":
    test_downstream()
