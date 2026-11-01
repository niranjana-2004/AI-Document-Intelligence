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
from app.core.security import create_access_token

client = TestClient(app)

def run_tests():
    db = SessionLocal()
    try:
        # 1. Find user and document 10
        user = db.query(User).filter(User.id == 4).first()
        if not user:
            user = db.query(User).first()
        assert user is not None, "User not found in DB"
        print(f"Testing with User #{user.id}: {user.email}")

        token = create_access_token(data={"sub": str(user.id)})
        headers = {"Authorization": f"Bearer {token}"}

        doc = db.query(Document).filter(
            Document.user_id == user.id,
            Document.is_handwritten == True
        ).order_by(Document.id.desc()).first()
        assert doc is not None, "Handwritten document not found"
        doc_id = doc.id
        print(f"Testing with Document #{doc_id}: {doc.filename}")

        # Check page transcription
        page = db.query(HandwrittenPage).filter(HandwrittenPage.document_id == doc_id).first()
        assert page is not None, "Document has no pages"
        text = page.edited_transcription or page.raw_transcription
        print(f"Page 1 has {len(text or '')} chars of transcription")

        # 2. Test intelligence-status
        print("\n--- 1. Testing intelligence-status ---")
        res = client.get(f"/handwritten/{doc_id}/intelligence-status", headers=headers)
        assert res.status_code == 200, f"Status failed: {res.text}"
        status_data = res.json()
        print(f"Status OK: has_transcription={status_data['has_transcription']}, hash={status_data['content_hash'][:10]}...")

        # 3. Test Summary Generation
        print("\n--- 2. Testing Smart Study Summary ---")
        res = client.post(
            f"/handwritten/{doc_id}/summary",
            json={"summary_type": "detailed"},
            headers=headers
        )
        assert res.status_code == 200, f"Summary post failed: {res.text}"
        summary_data = res.json()["summary"]
        print(f"Summary generated: Title = '{summary_data['title']}'")
        print(f"Overview preview: {summary_data['overview'][:100]}...")
        print(f"Takeaways count: {len(summary_data['takeaways'])}, Key terms: {len(summary_data['key_terms'])}")
        assert summary_data["is_outdated"] == False, "Summary should not be outdated immediately"

        # Test GET Summary
        res = client.get(f"/handwritten/{doc_id}/summary?type=detailed", headers=headers)
        assert res.status_code == 200
        assert res.json()["summary"]["title"] == summary_data["title"]

        # 4. Test Key Concept Extraction
        print("\n--- 3. Testing Concept Extraction ---")
        res = client.post(f"/handwritten/{doc_id}/concepts/generate", headers=headers)
        assert res.status_code == 200, f"Concepts post failed: {res.text}"
        concepts_data = res.json()
        concepts_list = concepts_data["concepts"]
        print(f"Extracted {len(concepts_list)} concepts")
        assert len(concepts_list) > 0, "No concepts extracted"
        first_concept = concepts_list[0]
        print(f"Concept 1: '{first_concept['name']}' -> {first_concept['definition'][:60]}...")

        # Test toggle bookmark
        expected_bookmark = not first_concept.get("is_bookmarked", False)
        res = client.patch(f"/handwritten/{doc_id}/concepts/{first_concept['id']}/bookmark", headers=headers)
        assert res.status_code == 200
        assert res.json()["is_bookmarked"] == expected_bookmark
        print(f"Bookmark toggled successfully for concept #{first_concept['id']} (now {expected_bookmark})")

        # 5. Test AI Quiz Generator
        print("\n--- 4. Testing AI Quiz Generator ---")
        res = client.post(
            f"/handwritten/{doc_id}/quizzes/generate",
            json={"difficulty": "medium", "question_count": 3, "question_types": "all"},
            headers=headers
        )
        assert res.status_code == 200, f"Quiz post failed: {res.text}"
        quiz_data = res.json()["quiz"]
        questions = quiz_data["questions"]
        print(f"Generated quiz '{quiz_data['title']}' with {len(questions)} questions")
        assert len(questions) > 0

        # Submit quiz answers
        answers_payload = {}
        for q in questions:
            answers_payload[q["id"]] = q.get("correct_answer", "")

        res = client.post(
            f"/handwritten/{doc_id}/quizzes/{quiz_data['id']}/submit",
            json={"answers": answers_payload},
            headers=headers
        )
        assert res.status_code == 200, f"Quiz submit failed: {res.text}"
        sub_res = res.json()
        print(f"Quiz submitted: Score = {sub_res['correct_count']}/{sub_res['total_questions']} ({sub_res['score_percentage']}%)")

        # 6. Test Flashcard Generator
        print("\n--- 5. Testing Flashcard Generator ---")
        res = client.post(
            f"/handwritten/{doc_id}/flashcards/generate",
            json={"card_count": 4},
            headers=headers
        )
        assert res.status_code == 200, f"Flashcards post failed: {res.text}"
        deck_data = res.json()["deck"]
        cards = deck_data["cards"]
        print(f"Generated deck '{deck_data['title']}' with {len(cards)} cards")
        assert len(cards) > 0
        first_card = cards[0]
        print(f"Card 1: Front='{first_card['front']}' | Back='{first_card['back'][:50]}...'")

        # Test update card status
        res = client.patch(
            f"/handwritten/{doc_id}/flashcards/{deck_data['id']}/cards/{first_card['id']}",
            json={"status": "known"},
            headers=headers
        )
        assert res.status_code == 200
        print(f"Card status updated to 'known'")

        # 7. Test Chat with Handwritten Notes
        print("\n--- 6. Testing Chat with Handwritten Notes (RAG) ---")
        res = client.post(
            f"/handwritten/{doc_id}/chat/message",
            json={"question": "What is the main topic or emotion expressed in these notes?"},
            headers=headers
        )
        assert res.status_code == 200, f"Chat message failed: {res.text}"
        chat_data = res.json()
        print(f"Assistant Answer: {chat_data['answer'][:120]}...")
        print(f"Citations count: {len(chat_data['sources'])}")

        # Test chat history
        res = client.get(f"/handwritten/{doc_id}/chat/history", headers=headers)
        assert res.status_code == 200
        history_msgs = res.json()["messages"]
        print(f"Chat history has {len(history_msgs)} messages")
        assert len(history_msgs) >= 2

        # 8. Test Invalidation on Edit
        print("\n--- 7. Testing Invalidation on Transcription Edit ---")
        # Save slightly edited text
        original_edited = page.edited_transcription
        temp_edited = (original_edited or "") + "\n\nAdditional verified note."
        res = client.put(
            f"/handwritten/{doc_id}/pages/1/transcription",
            json={"transcription": temp_edited},
            headers=headers
        )
        assert res.status_code == 200

        # Check if summary is now outdated
        res = client.get(f"/handwritten/{doc_id}/summary?type=detailed", headers=headers)
        assert res.status_code == 200
        assert res.json()["summary"]["is_outdated"] == True, "Summary must be marked outdated after transcription edit"
        print("Summary successfully marked as outdated after transcription modification!")

        # Revert page transcription to original
        res = client.put(
            f"/handwritten/{doc_id}/pages/1/transcription",
            json={"transcription": original_edited or ""},
            headers=headers
        )
        assert res.status_code == 200
        print("Transcription cleanly restored.")

        # 9. Test Tenant Isolation
        print("\n--- 8. Testing Tenant Isolation ---")
        # Fake token for user 9999
        fake_token = create_access_token(data={"sub": "999999"})
        fake_headers = {"Authorization": f"Bearer {fake_token}"}
        res = client.get(f"/handwritten/{doc_id}/summary?type=detailed", headers=fake_headers)
        # Should be 401 (user doesn't exist) or 404 (document not found)
        assert res.status_code in (401, 404), f"Unexpected status: {res.status_code}"
        print("Tenant isolation verified: Unauthorized user cannot access document intelligence.")

        print("\n==========================================")
        print("ALL PHASE 3 BACKEND TESTS PASSED SUCCESSFULLY!")
        print("==========================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()

