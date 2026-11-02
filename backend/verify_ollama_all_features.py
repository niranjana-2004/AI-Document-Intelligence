import os
import sys
import time
import json

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.user import User
from app.models.document import Document
from app.models.handwritten_page import HandwrittenPage
from app.core.security import create_access_token
from app.services.handwriting.ollama_client import check_ollama_health
from app.services.handwriting.handwritten_summary_service import generate_handwritten_summary
from app.services.handwriting.handwritten_concept_service import generate_handwritten_concepts
from app.services.handwriting.handwritten_quiz_service import generate_handwritten_quiz
from app.services.handwriting.handwritten_flashcard_service import generate_handwritten_flashcards
from app.services.handwriting.handwritten_chat_service import ask_handwritten_notes
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def verify_all_features():
    print("=" * 70)
    print("COGNIDOCS HANDWRITTEN AI - COMPREHENSIVE END-TO-END VERIFICATION")
    print("=" * 70)

    # 1. LIVE HEALTH CHECK
    print("\n[VERIFICATION 1/7] Centralized Health Check")
    t0 = time.time()
    health = check_ollama_health(force_refresh=True)
    dt_health = round((time.time() - t0) * 1000, 1)
    print(f"Status: {health['status']}")
    print(f"Message: {health['message']}")
    print(f"Base URL: {health['base_url']}")
    print(f"Required Model: {health['required_model']}")
    print(f"Installed Models: {health['available_models']}")
    print(f"Response Time: {health['response_time_ms']} ms (Python wrapper: {dt_health} ms)")
    assert health["status"] == "connected", f"Expected connected, got {health['status']}"

    # 2. FASTAPI HEALTH ENDPOINTS
    print("\n[VERIFICATION 2/7] FastAPI Health Endpoints")
    r1 = client.get("/ai/health")
    assert r1.status_code == 200, f"/ai/health returned {r1.status_code}"
    print(f"GET /ai/health -> HTTP 200 OK (status: {r1.json()['status']})")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == 4).first() or db.query(User).first()
        assert user is not None, "No test user found in DB"
        token = create_access_token(data={"sub": str(user.id)})
        headers = {"Authorization": f"Bearer {token}"}

        r2 = client.get("/handwritten/ai/health", headers=headers)
        assert r2.status_code == 200, f"/handwritten/ai/health returned {r2.status_code}"
        print(f"GET /handwritten/ai/health -> HTTP 200 OK (status: {r2.json()['status']})")

        # Pick document with transcriptions (Doc 12 or 13)
        doc = db.query(Document).filter(
            Document.user_id == user.id,
            Document.is_handwritten == True,
            Document.id == 13
        ).first()
        if not doc:
            doc = db.query(Document).filter(
                Document.user_id == user.id,
                Document.is_handwritten == True
            ).first()
        assert doc is not None, "No handwritten test document found"
        print(f"\nTarget Document: #{doc.id} ('{doc.filename}') | Owner: {user.email}")

        # 3. LIVE SUMMARY GENERATION
        print("\n[VERIFICATION 3/7] Live Study Summary Generation (Llama 3.2)")
        t0 = time.time()
        summary = generate_handwritten_summary(
            document_id=doc.id,
            user_id=user.id,
            db=db,
            summary_type="detailed"
        )
        dt_summary = round(time.time() - t0, 2)
        print(f"Generated in {dt_summary}s")
        print(f"Title: '{summary['title']}'")
        print(f"Overview: {summary['overview'][:140]}...")
        print(f"Takeaways count: {len(summary['takeaways'])}")
        print(f"Key terms count: {len(summary['key_terms'])}")
        assert summary["title"] and len(summary["takeaways"]) > 0

        # 4. LIVE CONCEPT EXTRACTION
        print("\n[VERIFICATION 4/7] Live Key Concept Extraction (Llama 3.2)")
        t0 = time.time()
        concepts_res = generate_handwritten_concepts(
            document_id=doc.id,
            user_id=user.id,
            db=db
        )
        dt_concepts = round(time.time() - t0, 2)
        concepts = concepts_res.get("concepts", [])
        print(f"Extracted {len(concepts)} concepts in {dt_concepts}s:")
        for idx, c in enumerate(concepts[:3]):
            print(f"  {idx+1}. {c['name']} (Page {c['page_number']}): {c['definition'][:80]}...")
        assert len(concepts) > 0

        # 5. LIVE QUIZ GENERATION
        print("\n[VERIFICATION 5/7] Live AI Quiz Generation (Llama 3.2)")
        t0 = time.time()
        quiz = generate_handwritten_quiz(
            document_id=doc.id,
            user_id=user.id,
            db=db,
            difficulty="medium",
            question_count=3,
            question_types="all"
        )
        dt_quiz = round(time.time() - t0, 2)
        questions = quiz.get("questions", [])
        print(f"Generated quiz '{quiz['title']}' with {len(questions)} questions in {dt_quiz}s:")
        for idx, q in enumerate(questions):
            q_text = q.get("question") or q.get("prompt") or ""
            print(f"  Q{idx+1} [{q.get('category', 'general')}] ({q.get('type', 'mcq')}): {q_text[:80]}...")
        assert len(questions) == 3

        # 6. LIVE FLASHCARD GENERATION
        print("\n[VERIFICATION 6/7] Live Flashcard Deck Generation (Llama 3.2)")
        t0 = time.time()
        deck = generate_handwritten_flashcards(
            document_id=doc.id,
            user_id=user.id,
            db=db,
            card_count=4
        )
        dt_flashcards = round(time.time() - t0, 2)
        cards = deck.get("cards", [])
        print(f"Generated deck '{deck['title']}' with {len(cards)} cards in {dt_flashcards}s:")
        for idx, card in enumerate(cards):
            card_type = card.get("card_type") or card.get("type") or "concept"
            print(f"  Card {idx+1} [{card_type}]: {card['front'][:60]}... -> {card['back'][:60]}...")
        assert len(cards) >= 3

        # 7. LIVE CHAT WITH NOTES (RAG)
        print("\n[VERIFICATION 7/7] Live Chat with Handwritten Notes (Hybrid RAG + Llama 3.2)")
        t0 = time.time()
        test_question = "What is CSS and what is its main role according to the notes?"
        chat_res = ask_handwritten_notes(
            document_id=doc.id,
            question=test_question,
            user_id=user.id,
            db=db
        )
        dt_chat = round(time.time() - t0, 2)
        print(f"Question: '{test_question}'")
        print(f"Answer ({dt_chat}s): {chat_res['answer'][:180]}...")
        print(f"Citations returned: {len(chat_res['sources'])}")
        assert chat_res["answer"] and len(chat_res["sources"]) > 0

        print("\n" + "=" * 70)
        print("SUCCESS: ALL 7 LIVE HANDWRITTEN AI FEATURES VERIFIED WORKING!")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    verify_all_features()
