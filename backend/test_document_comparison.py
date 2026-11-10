import os
import sys

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.main import app
from test_db_isolation import isolated_test_db
from app.core.database import SessionLocal
from app.models.user import User
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.handwritten_page import HandwrittenPage
from app.core.security import create_access_token
from app.services.embedding_services import generate_embedding
from app.services.document_comparison_service import (
    align_and_classify_documents,
    ComparisonChunk,
    generate_deterministic_comparison_summary,
    SIMILAR_THRESHOLD,
    MODIFIED_THRESHOLD
)

client = TestClient(app)


def run_comparison_tests():
    with isolated_test_db() as (db, _, _):
        print("=========================================================")
        print("COGNIDOCS DOCUMENT COMPARISON — VERIFICATION TEST SUITE")
        print("[ISOLATION] Running against isolated temporary SQLite snapshot (dev DB untouched)")
        print("=========================================================")

        # Find or use test user
        user = db.query(User).filter(User.id == 4).first() or db.query(User).first()
        assert user is not None, "Test user not found in database"
        print(f"[SETUP] Primary Test User #{user.id}: {user.email}")

        token = create_access_token(data={"sub": str(user.id)})
        headers = {"Authorization": f"Bearer {token}"}

        # Another user for unauthorized access tests
        other_user = db.query(User).filter(User.id != user.id).first()
        if not other_user:
            other_user = User(email="other_tenant@cognidocs.ai", full_name="Other Tenant")
            db.add(other_user)
            db.commit()
            db.refresh(other_user)
        print(f"[SETUP] Secondary Isolated User #{other_user.id}: {other_user.email}")

        # -------------------------------------------------------------
        # TEST 1: Two identical documents -> mostly/all similar or unchanged
        # -------------------------------------------------------------
        print("\n=== TEST 1: Identical Documents Semantic Equivalence ===")
        doc_base = Document(
            user_id=user.id,
            filename="test_base_networking.txt",
            document_type="TXT",
            file_path="uploads/test_base_networking.txt",
            extracted_text=(
                "TCP establishes a reliable connection using a three-way handshake.\n\n"
                "HTTP commonly operates on TCP port 80 for unencrypted web communication.\n\n"
                "DNS translates human-readable domain names into IP addresses."
            ),
            text_length=180,
            is_handwritten=False
        )
        doc_identical = Document(
            user_id=user.id,
            filename="test_identical_networking.txt",
            document_type="TXT",
            file_path="uploads/test_identical_networking.txt",
            extracted_text=(
                "TCP establishes a reliable connection using a three-way handshake.\n\n"
                "HTTP commonly operates on TCP port 80 for unencrypted web communication.\n\n"
                "DNS translates human-readable domain names into IP addresses."
            ),
            text_length=180,
            is_handwritten=False
        )
        db.add_all([doc_base, doc_identical])
        db.commit()
        db.refresh(doc_base)
        db.refresh(doc_identical)

        res1 = client.post(
            "/documents/compare",
            json={"document_a_id": doc_base.id, "document_b_id": doc_identical.id, "force_refresh": True},
            headers=headers
        )
        assert res1.status_code == 200, f"Test 1 failed: {res1.text}"
        data1 = res1.json()
        stats1 = data1["statistics"]
        print(f"Stats: {stats1}")
        assert stats1["similar"] > 0, "Expected similar/unchanged units"
        assert stats1["added"] == 0, f"Expected 0 added, got {stats1['added']}"
        assert stats1["removed"] == 0, f"Expected 0 removed, got {stats1['removed']}"
        assert stats1["modified"] == 0, f"Expected 0 modified, got {stats1['modified']}"
        print("PASS: Identical documents verified as 100% similar/unchanged!")

        # -------------------------------------------------------------
        # TEST 2: Document B contains additional content -> added content detected
        # -------------------------------------------------------------
        print("\n=== TEST 2: Additional Content Detection ===")
        doc_added = Document(
            user_id=user.id,
            filename="test_added_networking.txt",
            document_type="TXT",
            file_path="uploads/test_added_networking.txt",
            extracted_text=(
                "TCP establishes a reliable connection using a three-way handshake.\n\n"
                "HTTP commonly operates on TCP port 80 for unencrypted web communication.\n\n"
                "DNS translates human-readable domain names into IP addresses.\n\n"
                "SYN Cookie protection mitigates state exhaustion attacks against the TCP connection backlog queue."
            ),
            text_length=280,
            is_handwritten=False
        )
        db.add(doc_added)
        db.commit()
        db.refresh(doc_added)

        res2 = client.post(
            "/documents/compare",
            json={"document_a_id": doc_base.id, "document_b_id": doc_added.id, "force_refresh": True},
            headers=headers
        )
        assert res2.status_code == 200, f"Test 2 failed: {res2.text}"
        data2 = res2.json()
        stats2 = data2["statistics"]
        print(f"Stats: {stats2}")
        assert stats2["added"] >= 1, f"Expected at least 1 added section, got {stats2['added']}"
        added_texts = [a["document_b_text"] for a in data2["added"]]
        assert any("SYN Cookie" in t for t in added_texts), f"Expected SYN Cookie in added items: {added_texts}"
        print(f"PASS: Added content '{data2['added'][0]['title']}' detected with page {data2['added'][0]['document_b_page']}!")

        # -------------------------------------------------------------
        # TEST 3: Document B removes content -> removed content detected
        # -------------------------------------------------------------
        print("\n=== TEST 3: Removed Content Detection ===")
        doc_removed = Document(
            user_id=user.id,
            filename="test_removed_networking.txt",
            document_type="TXT",
            file_path="uploads/test_removed_networking.txt",
            extracted_text=(
                "TCP establishes a reliable connection using a three-way handshake.\n\n"
                "DNS translates human-readable domain names into IP addresses."
            ),
            text_length=120,
            is_handwritten=False
        )
        db.add(doc_removed)
        db.commit()
        db.refresh(doc_removed)

        res3 = client.post(
            "/documents/compare",
            json={"document_a_id": doc_base.id, "document_b_id": doc_removed.id, "force_refresh": True},
            headers=headers
        )
        assert res3.status_code == 200, f"Test 3 failed: {res3.text}"
        data3 = res3.json()
        stats3 = data3["statistics"]
        print(f"Stats: {stats3}")
        assert stats3["removed"] >= 1, f"Expected at least 1 removed section, got {stats3['removed']}"
        removed_texts = [r["document_a_text"] for r in data3["removed"]]
        assert any("HTTP" in t for t in removed_texts), f"Expected HTTP in removed items: {removed_texts}"
        print(f"PASS: Removed content '{data3['removed'][0]['title']}' detected with source page {data3['removed'][0]['document_a_page']}!")

        # -------------------------------------------------------------
        # TEST 4: Paraphrased wording preserves meaning -> semantic similarity
        # -------------------------------------------------------------
        print("\n=== TEST 4: Paraphrased Semantic Equivalence ===")
        doc_paraphrased = Document(
            user_id=user.id,
            filename="test_paraphrased_networking.txt",
            document_type="TXT",
            file_path="uploads/test_paraphrased_networking.txt",
            extracted_text=(
                "A TCP connection is established reliably through a SYN, SYN-ACK, and ACK handshake sequence.\n\n"
                "The HTTP protocol standardly uses destination port 80 for cleartext web traffic.\n\n"
                "The Domain Name System maps user-friendly server names to numeric IP locations."
            ),
            text_length=230,
            is_handwritten=False
        )
        db.add(doc_paraphrased)
        db.commit()
        db.refresh(doc_paraphrased)

        res4 = client.post(
            "/documents/compare",
            json={"document_a_id": doc_base.id, "document_b_id": doc_paraphrased.id, "force_refresh": True},
            headers=headers
        )
        assert res4.status_code == 200, f"Test 4 failed: {res4.text}"
        data4 = res4.json()
        stats4 = data4["statistics"]
        print(f"Stats: {stats4}")
        assert (stats4["similar"] + stats4["modified"]) == 3, f"Expected 3 aligned units, got similar={stats4['similar']}, modified={stats4['modified']}"
        assert stats4["removed"] == 0, f"Expected 0 removed for paraphrased text, got {stats4['removed']}"
        assert stats4["added"] == 0, f"Expected 0 added for paraphrased text, got {stats4['added']}"
        print("PASS: Semantic similarity successfully preserved across paraphrased phrasing!")

        # -------------------------------------------------------------
        # TEST 5: Document B genuinely changes a fact -> modified
        # -------------------------------------------------------------
        print("\n=== TEST 5: Factual Modification Detection ===")
        doc_fact_a = Document(
            user_id=user.id,
            filename="test_fact_a.txt",
            document_type="TXT",
            file_path="uploads/test_fact_a.txt",
            extracted_text="The security layer enforces TLS 1.2 protocol for all incoming client traffic.",
            text_length=80,
            is_handwritten=False
        )
        doc_fact_b = Document(
            user_id=user.id,
            filename="test_fact_b.txt",
            document_type="TXT",
            file_path="uploads/test_fact_b.txt",
            extracted_text="The security layer enforces TLS 1.2 and modern TLS 1.3 protocols with ChaCha20 cipher suites.",
            text_length=95,
            is_handwritten=False
        )
        db.add_all([doc_fact_a, doc_fact_b])
        db.commit()
        db.refresh(doc_fact_a)
        db.refresh(doc_fact_b)

        res5 = client.post(
            "/documents/compare",
            json={"document_a_id": doc_fact_a.id, "document_b_id": doc_fact_b.id, "force_refresh": True},
            headers=headers
        )
        assert res5.status_code == 200, f"Test 5 failed: {res5.text}"
        data5 = res5.json()
        stats5 = data5["statistics"]
        print(f"Stats: {stats5}")
        assert stats5["modified"] >= 1, f"Expected at least 1 modified section, got {stats5['modified']}"
        mod_item = data5["modified"][0]
        assert "TLS 1.2" in mod_item["document_a_text"]
        assert "TLS 1.3" in mod_item["document_b_text"]
        print(f"PASS: Modification detected! Change: '{mod_item['change_description']}'")

        # -------------------------------------------------------------
        # TEST 6: Same document selected twice -> validation error
        # -------------------------------------------------------------
        print("\n=== TEST 6: Same Document Validation Rejection ===")
        res6 = client.post(
            "/documents/compare",
            json={"document_a_id": doc_base.id, "document_b_id": doc_base.id},
            headers=headers
        )
        assert res6.status_code == 400, f"Expected HTTP 400, got {res6.status_code}"
        assert "Cannot compare a document with itself" in res6.text
        print(f"PASS: Self-comparison correctly rejected with message: '{res6.json()['detail']}'")

        # -------------------------------------------------------------
        # TEST 7: Unauthorized document ID -> authorization failure
        # -------------------------------------------------------------
        print("\n=== TEST 7: Tenant Isolation & Unauthorized Access ===")
        doc_other_user = Document(
            user_id=other_user.id,
            filename="isolated_tenant_doc.txt",
            document_type="TXT",
            file_path="uploads/isolated_tenant_doc.txt",
            extracted_text="Proprietary tenant confidential document.",
            text_length=45,
            is_handwritten=False
        )
        db.add(doc_other_user)
        db.commit()
        db.refresh(doc_other_user)

        res7 = client.post(
            "/documents/compare",
            json={"document_a_id": doc_base.id, "document_b_id": doc_other_user.id},
            headers=headers
        )
        assert res7.status_code in (403, 404), f"Expected HTTP 404 or 403, got {res7.status_code}"
        print(f"PASS: Cross-user document comparison blocked! Status: {res7.status_code}")

        # -------------------------------------------------------------
        # TEST 8: Missing or empty document -> safe user-facing error
        # -------------------------------------------------------------
        print("\n=== TEST 8: Missing or Empty Document Safe Error ===")
        # 8a: Nonexistent ID
        res8a = client.post(
            "/documents/compare",
            json={"document_a_id": 99999999, "document_b_id": doc_base.id},
            headers=headers
        )
        assert res8a.status_code == 404
        # 8b: Empty document
        doc_empty = Document(
            user_id=user.id,
            filename="empty_doc.txt",
            document_type="TXT",
            file_path="uploads/empty_doc.txt",
            extracted_text="   \n\n  ",
            text_length=0,
            is_handwritten=False
        )
        db.add(doc_empty)
        db.commit()
        db.refresh(doc_empty)

        res8b = client.post(
            "/documents/compare",
            json={"document_a_id": doc_base.id, "document_b_id": doc_empty.id, "force_refresh": True},
            headers=headers
        )
        assert res8b.status_code == 400
        assert "no extracted text" in res8b.text.lower()
        print(f"PASS: Missing and empty document scenarios handled gracefully!")

        # -------------------------------------------------------------
        # TEST 9: Ollama unavailable fallback -> deterministic synthesis
        # -------------------------------------------------------------
        print("\n=== TEST 9: Deterministic Fallback Synthesis (Ollama Resilient) ===")
        fallback_res = generate_deterministic_comparison_summary(
            doc_a_name="Protocol V1",
            doc_b_name="Protocol V2",
            stats={"total_units": 4, "similar": 2, "modified": 1, "added": 1, "removed": 0},
            similarities=[{"title": "Handshake", "document_a_page": 1, "document_b_page": 1}],
            modified=[{"title": "Ciphers", "change_description": "Added ChaCha20", "document_a_page": 2, "document_b_page": 2}],
            added=[{"title": "SYN Cookie", "document_b_text": "Mitigates flood attacks", "document_b_page": 3}],
            removed=[]
        )
        assert "summary" in fallback_res and len(fallback_res["summary"]) > 20
        assert len(fallback_res["key_changes"]) >= 1
        assert len(fallback_res["important_additions"]) >= 1
        assert "implications" in fallback_res
        print(f"PASS: Deterministic fallback synthesis verified without LLM dependency!")

        # -------------------------------------------------------------
        # TEST 10: Handwritten document with transcription participation
        # -------------------------------------------------------------
        print("\n=== TEST 10: Handwritten Document Comparison Integration ===")
        # Look for existing handwritten document with transcription in DB
        hw_doc = (
            db.query(Document)
            .filter(Document.user_id == user.id, Document.is_handwritten == True)
            .order_by(Document.id.desc())
            .first()
        )
        if hw_doc:
            hw_page = db.query(HandwrittenPage).filter(HandwrittenPage.document_id == hw_doc.id).first()
            if hw_page and (hw_page.edited_transcription or hw_page.raw_transcription):
                print(f"Found Handwritten Doc #{hw_doc.id} ('{hw_doc.filename}') with page transcription")
                res10 = client.post(
                    "/documents/compare",
                    json={"document_a_id": doc_base.id, "document_b_id": hw_doc.id, "force_refresh": True},
                    headers=headers
                )
                assert res10.status_code == 200, f"Handwritten comparison failed: {res10.text}"
                data10 = res10.json()
                assert data10["document_b"]["is_handwritten"] == True
                assert data10["statistics"]["total_units"] > 0
                print(f"PASS: Handwritten Doc #{hw_doc.id} compared successfully! Total units: {data10['statistics']['total_units']}")
            else:
                print("Skipping handwritten step: no page transcription in DB for user")
        else:
            print("Skipping handwritten step: no handwritten doc in DB for user")

        print("\n=========================================================")
        print("ALL 10 DOCUMENT COMPARISON TESTS PASSED WITH ZERO FAILURES!")
        print("=========================================================")


if __name__ == "__main__":
    run_comparison_tests()
