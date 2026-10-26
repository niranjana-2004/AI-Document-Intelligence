import unittest
from unittest.mock import patch

from starlette.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
from app.models.user import User
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.activity import ActivityLog
from app.core.security import hash_password, create_access_token
from app.services.similarity_service import cosine_similarity
from app.services.search_service import (
    calculate_keyword_score,
    expand_query,
    detect_query_intent,
    detect_query_category,
    calculate_category_boost,
    calculate_subsection_boost,
    semantic_search,
)


class TestSearchService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure an isolated in-memory SQLite database
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=cls.engine
        )
        Base.metadata.create_all(bind=cls.engine)

        def override_get_db():
            db = cls.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=cls.engine)

    def setUp(self):
        # Clean up database tables between test cases
        self.db = self.TestingSessionLocal()
        self.db.query(ActivityLog).delete()
        self.db.query(DocumentChunk).delete()
        self.db.query(Document).delete()
        self.db.query(User).delete()
        self.db.commit()

    def tearDown(self):
        self.db.close()

    # -------------------------------------------------------------------------
    # Unit Tests: Cosine Similarity
    # -------------------------------------------------------------------------

    def test_cosine_similarity_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        sim = cosine_similarity(v, v)
        self.assertAlmostEqual(sim, 1.0, places=5)

    def test_cosine_similarity_orthogonal_vectors(self):
        v1 = [1.0, 0.0]
        v2 = [0.0, 1.0]
        sim = cosine_similarity(v1, v2)
        self.assertAlmostEqual(sim, 0.0, places=5)

    def test_cosine_similarity_opposite_vectors(self):
        v1 = [1.0, 2.0]
        v2 = [-1.0, -2.0]
        sim = cosine_similarity(v1, v2)
        self.assertAlmostEqual(sim, -1.0, places=5)

    def test_cosine_similarity_zero_vector(self):
        v1 = [0.0, 0.0, 0.0]
        v2 = [1.0, 2.0, 3.0]
        sim = cosine_similarity(v1, v2)
        self.assertEqual(sim, 0.0)

    def test_cosine_similarity_dimension_mismatch(self):
        v1 = [1.0, 2.0]
        v2 = [1.0, 2.0, 3.0]
        with self.assertRaises(ValueError):
            cosine_similarity(v1, v2)

    # -------------------------------------------------------------------------
    # Unit Tests: Keyword Scoring and Query Expansion
    # -------------------------------------------------------------------------

    def test_calculate_keyword_score_exact_match(self):
        query = "python fastapi"
        content = "This document is about Python and FastAPI development."
        score = calculate_keyword_score(query, content)
        self.assertEqual(score, 1.0)

    def test_calculate_keyword_score_partial_overlap(self):
        query = "python react docker"
        content = "We use Python and React in the frontend."
        score = calculate_keyword_score(query, content)
        self.assertAlmostEqual(score, 2.0 / 3.0, places=4)

    def test_calculate_keyword_score_stopwords_only(self):
        query = "the and or of with"
        content = "Some content without matches."
        score = calculate_keyword_score(query, content)
        self.assertEqual(score, 0.0)

    def test_calculate_keyword_score_abbreviation_expansion(self):
        query = "bca graduate"
        content = "Holds a Bachelor of Computer Applications from University."
        score = calculate_keyword_score(query, content)
        self.assertAlmostEqual(score, 0.5, places=4)

    def test_expand_query(self):
        expanded = expand_query("completed BCA and MCA")
        self.assertIn("Bachelor of Computer Applications", expanded)
        self.assertIn("Master of Computer Applications", expanded)

    def test_detect_query_intent(self):
        self.assertEqual(detect_query_intent("what are the programming languages used?"), "programming_languages")
        self.assertEqual(detect_query_intent("tell me about the projects done"), "projects")
        self.assertIsNone(detect_query_intent("random query without intent"))

    # -------------------------------------------------------------------------
    # Integration Tests: Semantic Search Core Logic & User Isolation
    # -------------------------------------------------------------------------

    def test_semantic_search_user_isolation(self):
        # User 1
        user1 = User(id=1, email="user1@example.com", full_name="User One", password_hash=hash_password("Pass1!"), is_verified=True)
        # User 2
        user2 = User(id=2, email="user2@example.com", full_name="User Two", password_hash=hash_password("Pass2!"), is_verified=True)
        self.db.add_all([user1, user2])
        self.db.commit()

        # Doc 1 for User 1
        doc1 = Document(id=1, user_id=1, filename="user1_doc.txt", document_type="TXT", file_path="uploads/user1_doc.txt")
        # Doc 2 for User 2
        doc2 = Document(id=2, user_id=2, filename="user2_doc.txt", document_type="TXT", file_path="uploads/user2_doc.txt")
        self.db.add_all([doc1, doc2])
        self.db.commit()

        # Chunks
        chunk1 = DocumentChunk(
            id=1, document_id=1, chunk_index=0,
            content="Confidential financial report for User One.",
            embedding=[1.0, 0.0, 0.0, 0.0]
        )
        chunk2 = DocumentChunk(
            id=2, document_id=2, chunk_index=0,
            content="Confidential financial report for User Two.",
            embedding=[1.0, 0.0, 0.0, 0.0]
        )
        self.db.add_all([chunk1, chunk2])
        self.db.commit()

        # User 1 searches: should only see User 1 chunk
        with patch("app.services.search_service.generate_embedding", return_value=[1.0, 0.0, 0.0, 0.0]):
            res_user1 = semantic_search(query="financial report", db=self.db, user_id=1, top_k=5)
            self.assertEqual(len(res_user1), 1)
            self.assertEqual(res_user1[0]["chunk_id"], 1)
            self.assertEqual(res_user1[0]["filename"], "user1_doc.txt")

            # User 2 searches: should only see User 2 chunk
            res_user2 = semantic_search(query="financial report", db=self.db, user_id=2, top_k=5)
            self.assertEqual(len(res_user2), 1)
            self.assertEqual(res_user2[0]["chunk_id"], 2)
            self.assertEqual(res_user2[0]["filename"], "user2_doc.txt")

    def test_semantic_search_missing_embedding_handling(self):
        user = User(id=1, email="user@example.com", full_name="User", password_hash=hash_password("Pass1!"), is_verified=True)
        doc = Document(id=1, user_id=1, filename="doc.txt", document_type="TXT", file_path="uploads/doc.txt")
        self.db.add_all([user, doc])
        self.db.commit()

        # One chunk has None for embedding
        chunk_no_emb = DocumentChunk(
            id=1, document_id=1, chunk_index=0,
            content="Text with missing vector embedding.",
            embedding=None
        )
        chunk_with_emb = DocumentChunk(
            id=2, document_id=1, chunk_index=1,
            content="Text with valid vector embedding.",
            embedding=[0.5, 0.5, 0.5, 0.5]
        )
        self.db.add_all([chunk_no_emb, chunk_with_emb])
        self.db.commit()

        with patch("app.services.search_service.generate_embedding", return_value=[0.5, 0.5, 0.5, 0.5]):
            # Should not raise any error and should safely skip chunk_no_emb
            results = semantic_search(query="valid vector", db=self.db, user_id=1, top_k=5)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["chunk_id"], 2)

    def test_semantic_search_document_id_filtering(self):
        user = User(id=1, email="user@example.com", full_name="User", password_hash=hash_password("Pass1!"), is_verified=True)
        doc1 = Document(id=1, user_id=1, filename="doc1.txt", document_type="TXT", file_path="uploads/doc1.txt")
        doc2 = Document(id=2, user_id=1, filename="doc2.txt", document_type="TXT", file_path="uploads/doc2.txt")
        self.db.add_all([user, doc1, doc2])
        self.db.commit()

        chunk1 = DocumentChunk(id=1, document_id=1, chunk_index=0, content="Document 1 content.", embedding=[0.5, 0.5])
        chunk2 = DocumentChunk(id=2, document_id=2, chunk_index=0, content="Document 2 content.", embedding=[0.5, 0.5])
        self.db.add_all([chunk1, chunk2])
        self.db.commit()

        with patch("app.services.search_service.generate_embedding", return_value=[0.5, 0.5]):
            results = semantic_search(query="content", db=self.db, user_id=1, document_id=2, top_k=5)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["document_id"], 2)

    # -------------------------------------------------------------------------
    # API Endpoint Tests: GET /documents/search
    # -------------------------------------------------------------------------

    def test_search_endpoint_unauthorized(self):
        response = self.client.get("/documents/search?query=test")
        self.assertEqual(response.status_code, 401)

    def test_search_endpoint_empty_query(self):
        user = User(id=1, email="test@example.com", full_name="Tester", password_hash=hash_password("Pass1!"), is_verified=True)
        self.db.add(user)
        self.db.commit()
        token = create_access_token({"sub": str(user.id)})

        response = self.client.get(
            "/documents/search?query=   ",
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Search query cannot be empty", response.json()["detail"])

    def test_search_endpoint_invalid_top_k(self):
        user = User(id=1, email="test@example.com", full_name="Tester", password_hash=hash_password("Pass1!"), is_verified=True)
        self.db.add(user)
        self.db.commit()
        token = create_access_token({"sub": str(user.id)})

        # top_k < 1
        resp_low = self.client.get(
            "/documents/search?query=test&top_k=0",
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(resp_low.status_code, 400)

        # top_k > 20
        resp_high = self.client.get(
            "/documents/search?query=test&top_k=25",
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(resp_high.status_code, 400)

    def test_search_endpoint_success_and_activity_logging(self):
        user = User(id=1, email="test@example.com", full_name="Tester", password_hash=hash_password("Pass1!"), is_verified=True)
        doc = Document(id=1, user_id=1, filename="test.pdf", document_type="PDF", file_path="uploads/test.pdf")
        chunk = DocumentChunk(
            id=1, document_id=1, chunk_index=0,
            content="FastAPI is a modern web framework for Python.",
            embedding=[0.8, 0.2, 0.1, 0.0]
        )
        self.db.add_all([user, doc, chunk])
        self.db.commit()
        token = create_access_token({"sub": str(user.id)})

        with patch("app.services.search_service.generate_embedding", return_value=[0.8, 0.2, 0.1, 0.0]):
            response = self.client.get(
                "/documents/search?query=FastAPI%20framework&top_k=5",
                headers={"Authorization": f"Bearer {token}"}
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["query"], "FastAPI framework")
        self.assertEqual(data["result_count"], 1)
        self.assertEqual(len(data["results"]), 1)

        result = data["results"][0]
        self.assertEqual(result["chunk_id"], 1)
        self.assertEqual(result["filename"], "test.pdf")
        self.assertIn("similarity", result)
        self.assertIn("final_score", result)
        self.assertIn("content", result)

        # Verify activity was logged
        activity = self.db.query(ActivityLog).filter_by(user_id=1, activity_type="search").first()
        self.assertIsNotNone(activity)


if __name__ == "__main__":
    unittest.main()
