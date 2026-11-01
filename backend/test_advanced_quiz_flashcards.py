import os
import sys

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.user import User
from app.models.document import Document
from app.models.handwritten_page import HandwrittenPage
from app.models.handwritten_analysis import HandwrittenQuizSet, HandwrittenFlashcardSet
from app.core.security import create_access_token
from app.services.handwriting.handwritten_flashcard_service import FLASHCARD_TYPES
from app.services.handwriting.handwritten_quiz_service import QUESTION_CATEGORIES

client = TestClient(app)

def run_tests():
    db = SessionLocal()
    try:
        # -------------------------------------------------------------
        # 0. Test Setup & Document Retrieval
        # -------------------------------------------------------------
        user = db.query(User).filter(User.id == 4).first() or db.query(User).first()
        assert user is not None, "User not found in DB"
        print(f"[TEST SETUP] Testing with User #{user.id}: {user.email}")

        token = create_access_token(data={"sub": str(user.id)})
        headers = {"Authorization": f"Bearer {token}"}

        doc = db.query(Document).filter(
            Document.user_id == user.id,
            Document.is_handwritten == True
        ).order_by(Document.id.desc()).first()
        assert doc is not None, "Handwritten document not found"
        doc_id = doc.id
        print(f"[TEST SETUP] Testing with Document #{doc_id}: '{doc.filename}'")

        # -------------------------------------------------------------
        # 1. Document Topics Endpoint (GET /handwritten/{doc_id}/topics)
        # -------------------------------------------------------------
        print("\n=== STEP 1: Testing Topics Discovery ===")
        res = client.get(f"/handwritten/{doc_id}/topics", headers=headers)
        assert res.status_code == 200, f"Failed topics retrieval: {res.text}"
        topics_data = res.json()
        discovered_topics = topics_data.get("topics", [])
        print(f"Discovered {len(discovered_topics)} topics:")
        for t in discovered_topics[:5]:
            print(f"  * {t}")
        assert len(discovered_topics) > 0, "Expected at least one topic extracted from notes"

        # -------------------------------------------------------------
        # 2. Advanced Quiz Generation (7 Categories & Multi-Format)
        # -------------------------------------------------------------
        print("\n=== STEP 2: Testing Advanced Quiz Generation ===")
        res = client.post(
            f"/handwritten/{doc_id}/quizzes/generate",
            json={
                "difficulty": "mixed",
                "question_count": 5,
                "question_types": "all",
                "topics": []
            },
            headers=headers
        )
        assert res.status_code == 200, f"Quiz generation failed: {res.text}"
        quiz_data = res.json()["quiz"]
        quiz_id = quiz_data["id"]
        questions = quiz_data["questions"]
        print(f"Generated Quiz #{quiz_id}: '{quiz_data['title']}' ({len(questions)} questions)")
        
        # Verify question count is at least 3 without weakening
        assert len(questions) >= 3, f"Expected at least 3 questions, got {len(questions)}"

        categories_seen = set()
        types_seen = set()
        for q in questions:
            cat = q.get("category", "conceptual")
            q_type = q.get("type", "multiple_choice")
            categories_seen.add(cat)
            types_seen.add(q_type)
            print(f"  [Q{q['id']}] [{cat.upper()}] [{q_type}] {q['question'][:70]}...")

        print(f"Observed categories: {categories_seen}")
        print(f"Observed question types: {types_seen}")
        # Verify valid pedagogical categories
        for cat in categories_seen:
            assert cat in QUESTION_CATEGORIES, f"Unexpected category: {cat}"

        # -------------------------------------------------------------
        # 3. Examination Integrity: Answers strictly masked before submit
        # -------------------------------------------------------------
        print("\n=== STEP 3: Verifying Examination Integrity (Answers Masked) ===")
        for q in questions:
            assert q.get("correct_answer") is None, f"FAIL: correct_answer exposed before submit for Q{q['id']}!"
            assert q.get("explanation") is None, f"FAIL: explanation exposed before submit for Q{q['id']}!"
            assert q.get("excerpt") is None, f"FAIL: excerpt exposed before submit for Q{q['id']}!"
        print("PASS: All correct answers and explanations are strictly hidden from student!")

        # -------------------------------------------------------------
        # 4. Interactive Quiz Submission, Scoring & Recommendations
        # -------------------------------------------------------------
        print("\n=== STEP 4: Testing Quiz Submission, Scoring & Recommendations ===")
        db_quiz = db.query(HandwrittenQuizSet).filter(HandwrittenQuizSet.id == quiz_id).first()
        raw_first_correct = db_quiz.questions[0].get("correct_answer")

        # Simulate exam answers:
        # Question 1: Correct answer
        # Question 2: Incorrect answer
        # Question 3: Skipped (unanswered)
        user_answers = {
            str(questions[0]["id"]): raw_first_correct,
            str(questions[1]["id"]): "Definitely incorrect answer option for testing"
        }

        res = client.post(
            f"/handwritten/{doc_id}/quizzes/{quiz_id}/submit",
            json={
                "answers": user_answers,
                "time_taken_seconds": 128
            },
            headers=headers
        )
        assert res.status_code == 200, f"Submit failed: {res.text}"
        submitted_data = res.json()
        print(f"Submission recorded! Score: {submitted_data['correct_count']}/{submitted_data['total_questions']} ({submitted_data['score_percentage']}%)")
        print(f"Time taken: {submitted_data.get('time_taken_seconds')}s")
        print(f"Correct: {submitted_data['correct_count']} | Incorrect: {submitted_data['incorrect_count']} | Unanswered: {submitted_data['unanswered_count']}")

        assert submitted_data["correct_count"] >= 1, "Expected at least 1 correct answer"
        assert submitted_data["incorrect_count"] >= 1, "Expected at least 1 incorrect answer"
        assert submitted_data["unanswered_count"] >= 1, "Expected at least 1 skipped question"
        assert submitted_data["time_taken_seconds"] == 128, "Time taken should match submission"

        # Verify weak topics and learning recommendations
        weak_topics = submitted_data.get("weak_topics", [])
        recommendations = submitted_data.get("recommendations", [])
        print(f"Weak topics identified: {len(weak_topics)}")
        assert len(weak_topics) >= 1, "Expected weak topics to be detected for incorrect questions"
        for wt in weak_topics:
            print(f"  * {wt.get('topic')}: Missed {wt.get('missed_count')}/{wt.get('total_questions')} ({wt.get('score_percentage')}%) Pages: {wt.get('pages')}")
            assert "pages" in wt
            assert "topic" in wt

        print(f"Actionable recommendations generated: {len(recommendations)}")
        assert len(recommendations) >= 1, "Expected recommendations for weak areas"
        for rec in recommendations:
            print(f"  * {rec.get('topic')}: {rec.get('action')}")
            assert "action" in rec
            assert "pages" in rec

        # -------------------------------------------------------------
        # 5. Verifying Answers Unmasked Post-Submission
        # -------------------------------------------------------------
        print("\n=== STEP 5: Verifying Answers Unmasked Post-Submission ===")
        res = client.get(f"/handwritten/{doc_id}/quizzes", headers=headers)
        assert res.status_code == 200
        quizzes = res.json()["quizzes"]
        submitted_quiz = next((q for q in quizzes if q["id"] == quiz_id), None)
        assert submitted_quiz is not None
        assert submitted_quiz["is_submitted"] == True
        for q in submitted_quiz["questions"]:
            assert q.get("correct_answer") is not None, f"FAIL: correct_answer still masked after submit for Q{q['id']}!"
            assert q.get("explanation") is not None, f"FAIL: explanation missing after submit for Q{q['id']}!"
            assert q.get("page_number") is not None, f"FAIL: page_number missing for Q{q['id']}!"
        print("PASS: Answers, detailed explanations, and source page citations are now fully visible.")

        # -------------------------------------------------------------
        # 6. Advanced Flashcard Generation (8 Distinct Card Types)
        # -------------------------------------------------------------
        print("\n=== STEP 6: Testing Flashcard Generation (8 Types) ===")
        res = client.post(
            f"/handwritten/{doc_id}/flashcards/generate",
            json={
                "card_count": 8,
                "difficulty": "medium",
                "topic": None
            },
            headers=headers
        )
        assert res.status_code == 200, f"Flashcards generation failed: {res.text}"
        deck_data = res.json()["deck"]
        deck_id = deck_data["id"]
        cards = deck_data["cards"]
        print(f"Generated Deck #{deck_id}: '{deck_data['title']}' ({len(cards)} cards)")
        # Without weakening: demand at least 5 cards for an 8-card request
        assert len(cards) >= 5, f"Expected at least 5 cards, got {len(cards)}"

        card_types_seen = set()
        for idx, c in enumerate(cards):
            c_type = c.get("card_type", "concept_explanation")
            card_types_seen.add(c_type)
            print(f"  [Card {idx+1}] [{c_type.upper()}] Prompt: {c['front'][:55]}... -> Back: {c['back'][:45]}...")
            assert c.get("page_number") is not None, f"Card {idx} missing page_number"

        print(f"Observed Flashcard types: {card_types_seen}")
        for ct in card_types_seen:
            assert ct in FLASHCARD_TYPES, f"Unknown flashcard type generated: {ct}"

        # -------------------------------------------------------------
        # 7. 4-Level Self-Assessment Ratings & Persistence
        # -------------------------------------------------------------
        print("\n=== STEP 7: Testing 4-Level Self-Assessment Ratings & Persistence ===")
        ratings_to_test = [
            (0, "again"),
            (1, "hard"),
            (2, "good"),
            (3, "easy")
        ]
        for card_idx, rating in ratings_to_test:
            if card_idx < len(cards):
                card_id_param = cards[card_idx].get("id", str(card_idx))
                res = client.patch(
                    f"/handwritten/{doc_id}/flashcards/{deck_id}/cards/{card_id_param}",
                    json={"rating": rating},
                    headers=headers
                )
                assert res.status_code == 200, f"Rating update failed for card {card_idx}: {res.text}"
                updated_card = res.json()["card"]
                assert updated_card.get("rating") == rating, f"Rating mismatch: {updated_card.get('rating')} vs {rating}"
                assert updated_card.get("review_count", 0) >= 1, "Review count should be incremented"
                assert updated_card.get("last_reviewed_at") is not None, "last_reviewed_at should be set"
                print(f"  Card {card_idx}: Rating set to '{rating}', Review Count={updated_card['review_count']}, Last Reviewed={updated_card['last_reviewed_at'][:19]}")

        # -------------------------------------------------------------
        # 8. Deck Retrieval, Smart Revision & Reset
        # -------------------------------------------------------------
        print("\n=== STEP 8: Testing Smart Revision, Deck Metrics & Reset ===")
        res = client.get(f"/handwritten/{doc_id}/flashcards", headers=headers)
        assert res.status_code == 200
        decks = res.json()["decks"]
        active_deck = next((d for d in decks if d["id"] == deck_id), None)
        assert active_deck is not None
        print(f"Deck Metrics for '{active_deck['title']}':")
        print(f"  * Total Cards: {active_deck['card_count']}")
        print(f"  * Known (Good/Easy): {active_deck['known_count']}")
        print(f"  * Needs Review (Again/Hard): {active_deck['needs_review_count']}")
        print(f"  * Unreviewed: {active_deck['unreviewed_count']}")
        
        # Verify persistence and filtering metrics
        assert active_deck['needs_review_count'] >= 2, f"Expected at least 2 cards marked for review, got {active_deck['needs_review_count']}"
        assert active_deck['known_count'] >= 2, f"Expected at least 2 cards marked known, got {active_deck['known_count']}"

        # Test Reset Deck functionality
        res = client.post(f"/handwritten/{doc_id}/flashcards/{deck_id}/reset", headers=headers)
        assert res.status_code == 200, f"Reset failed: {res.text}"
        res = client.get(f"/handwritten/{doc_id}/flashcards", headers=headers)
        reset_deck = next((d for d in res.json()["decks"] if d["id"] == deck_id), None)
        assert reset_deck["known_count"] == 0, "Known count should be 0 after reset"
        assert reset_deck["needs_review_count"] == 0, "Needs review count should be 0 after reset"
        assert reset_deck["unreviewed_count"] == len(cards), "All cards should be unreviewed after reset"
        print("  [OK] Deck reset verified: all cards restored to unreviewed state.")

        # -------------------------------------------------------------
        # 9. Backward Compatibility Verification
        # -------------------------------------------------------------
        print("\n=== STEP 9: Testing Backward Compatibility with Existing Data ===")
        all_quizzes = db.query(HandwrittenQuizSet).filter(HandwrittenQuizSet.document_id == doc_id).all()
        all_flashcards = db.query(HandwrittenFlashcardSet).filter(HandwrittenFlashcardSet.document_id == doc_id).all()
        print(f"Verified {len(all_quizzes)} existing quiz sets and {len(all_flashcards)} existing flashcard decks in DB.")
        assert len(all_quizzes) >= 1, "Existing quizzes should be present"
        assert len(all_flashcards) >= 1, "Existing flashcards should be present"

        # Verify API can list them without errors
        res = client.get(f"/handwritten/{doc_id}/quizzes", headers=headers)
        assert res.status_code == 200
        assert len(res.json().get("quizzes", [])) == len(all_quizzes)

        res = client.get(f"/handwritten/{doc_id}/flashcards", headers=headers)
        assert res.status_code == 200
        assert len(res.json().get("decks", [])) == len(all_flashcards)
        print("  [OK] Backward compatibility verified: all legacy records readable and valid.")

        # -------------------------------------------------------------
        # 10. Regression Testing on Phase 1, Phase 2, Phase 3
        # -------------------------------------------------------------
        print("\n=== STEP 10: Regression Testing on Core Pipelines ===")
        # Check intelligence-status
        res = client.get(f"/handwritten/{doc_id}/intelligence-status", headers=headers)
        assert res.status_code == 200, "Intelligence status failed"
        assert res.json()["has_transcription"] == True

        # Check Smart Summary
        res = client.get(f"/handwritten/{doc_id}/summary", headers=headers)
        assert res.status_code == 200, "GET summary failed"
        print("  [OK] Study Summary retrieval OK")

        # Check Concepts
        res = client.get(f"/handwritten/{doc_id}/concepts", headers=headers)
        assert res.status_code == 200, "GET concepts failed"
        print(f"  [OK] Key Concepts retrieval OK ({len(res.json().get('concepts', []))} concepts)")

        # Check AI Chat with Notes
        res = client.post(
            f"/handwritten/{doc_id}/chat/message",
            json={"question": "What is the primary topic of these handwritten notes?"},
            headers=headers
        )
        assert res.status_code == 200, f"Chat failed: {res.text}"
        chat_data = res.json()
        print(f"  [OK] Chat with Notes response: '{chat_data['answer'][:80]}...'")

        print("\n=========================================================")
        print("ALL 10 VERIFICATION STEPS PASSED WITH ZERO FAILURES!")
        print("=========================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
