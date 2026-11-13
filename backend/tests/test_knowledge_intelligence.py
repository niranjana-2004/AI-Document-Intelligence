import sys
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.handwritten_page import HandwrittenPage
from app.models.research_paper_analysis import ResearchPaperAnalysis, ensure_research_paper_analysis_schema
from app.models.knowledge_graph import (
    KnowledgeGraph,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    ensure_knowledge_graph_schema,
)
from app.models.cross_document_knowledge_graph import (
    CanonicalEntity,
    CrossDocumentEdge,
    CrossDocumentKnowledgeGraph,
    EntityOccurrence,
    ensure_cross_document_knowledge_graph_schema,
)
from app.models.knowledge_intelligence_cache import (
    KnowledgeIntelligenceCache,
    ensure_knowledge_intelligence_schema,
)
from app.models.user import User
from app.schemas.cross_document_knowledge_graph import CanonicalEntityOut, CrossDocumentEdgeOut
from app.schemas.knowledge_intelligence import (
    KnowledgeIntelligenceQueryRequest,
    KnowledgeIntelligenceResponse,
)
from app.services.knowledge_intelligence_service import (
    detect_cross_document_insights_and_conflicts,
    execute_knowledge_intelligence_query,
    match_query_to_canonical_entities,
    parse_knowledge_query,
    retrieve_multi_source_evidence,
    synthesize_grounded_answer,
)


class KnowledgeIntelligenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.TestingSessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=cls.engine,
        )
        Base.metadata.create_all(bind=cls.engine)
        ensure_knowledge_graph_schema(cls.engine)
        ensure_cross_document_knowledge_graph_schema(cls.engine)
        ensure_research_paper_analysis_schema(cls.engine)
        ensure_knowledge_intelligence_schema(cls.engine)

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
        self.db = self.TestingSessionLocal()
        self.db.query(KnowledgeIntelligenceCache).delete()
        self.db.query(EntityOccurrence).delete()
        self.db.query(CrossDocumentEdge).delete()
        self.db.query(CanonicalEntity).delete()
        self.db.query(CrossDocumentKnowledgeGraph).delete()
        self.db.query(KnowledgeGraphEdge).delete()
        self.db.query(KnowledgeGraphNode).delete()
        self.db.query(KnowledgeGraph).delete()
        self.db.query(ResearchPaperAnalysis).delete()
        self.db.query(HandwrittenPage).delete()
        self.db.query(DocumentChunk).delete()
        self.db.query(Document).delete()
        self.db.query(User).delete()
        self.db.commit()

        # Seed User 1 (Authorized Owner)
        self.user1 = User(
            email="intelligence_tester1@cognidocs.ai",
            password_hash=hash_password("password123"),
            full_name="Intelligence Tester One",
            is_verified=True,
        )
        # Seed User 2 (Adversarial Tenant)
        self.user2 = User(
            email="intelligence_tester2@cognidocs.ai",
            password_hash=hash_password("password123"),
            full_name="Intelligence Tester Two",
            is_verified=True,
        )
        self.db.add_all([self.user1, self.user2])
        self.db.commit()
        self.db.refresh(self.user1)
        self.db.refresh(self.user2)

        self.token_user1 = create_access_token({"sub": str(self.user1.id)})
        self.token_user2 = create_access_token({"sub": str(self.user2.id)})
        self.headers_user1 = {"Authorization": f"Bearer {self.token_user1}"}
        self.headers_user2 = {"Authorization": f"Bearer {self.token_user2}"}

    def tearDown(self):
        self.db.close()

    def test_query_understanding_intent_and_extraction(self):
        """Test deterministic intent classification, candidate extraction, and acronym parsing."""
        # Case 1: Cross-document synthesis query
        q1 = "What do my documents say about TCP?"
        p1 = parse_knowledge_query(q1)
        self.assertEqual(p1["intent"], "cross_document_synthesis")
        self.assertIn("TCP", p1["candidate_entities"])
        self.assertIn("TCP", p1["acronyms"])

        # Case 2: Comparison query
        q2 = "Compare TCP and UDP in terms of reliability"
        p2 = parse_knowledge_query(q2)
        self.assertEqual(p2["intent"], "entity_comparison")
        self.assertTrue(p2["comparison_requested"])
        self.assertIn("TCP", p2["candidate_entities"])
        self.assertIn("UDP", p2["candidate_entities"])

        # Case 3: Conflict / disagreement query
        q3 = "Which documents disagree about connection handling?"
        p3 = parse_knowledge_query(q3)
        self.assertEqual(p3["intent"], "conflict_detection")
        self.assertTrue(p3["conflict_requested"])

        # Case 4: Evidence audit query
        q4 = "Show me all the evidence for AES encryption"
        p4 = parse_knowledge_query(q4)
        self.assertEqual(p4["intent"], "evidence_audit")
        self.assertTrue(p4["evidence_requested"])

        # Case 5: Relationship query
        q5 = "How are CNN and image classification related?"
        p5 = parse_knowledge_query(q5)
        self.assertEqual(p5["intent"], "relationship_query")
        self.assertTrue(p5["relationship_requested"])

    def test_entity_resolution_and_adversarial_guardrails(self):
        """Test matching query tokens to canonical entities with strict disambiguation."""
        canonical_entities = [
            CanonicalEntityOut(
                entity_key="concept:tcp",
                canonical_name="Transmission Control Protocol",
                normalized_name="transmission control protocol",
                entity_type="Protocol",
                aliases=["TCP", "TCP/IP"],
                confidence=0.95,
                importance_score=0.9,
                document_count=2,
                occurrence_count=5,
                is_shared=True,
            ),
            CanonicalEntityOut(
                entity_key="concept:udp",
                canonical_name="User Datagram Protocol",
                normalized_name="user datagram protocol",
                entity_type="Protocol",
                aliases=["UDP"],
                confidence=0.90,
                importance_score=0.7,
                document_count=1,
                occurrence_count=2,
                is_shared=False,
            ),
            CanonicalEntityOut(
                entity_key="concept:java_prog",
                canonical_name="Java",
                normalized_name="java",
                entity_type="Programming Language",
                description="Java is an object-oriented programming language executed on the JVM.",
                aliases=["Java Language"],
                confidence=0.92,
                importance_score=0.8,
            ),
        ]

        # 1. Match TCP acronym
        m_tcp = match_query_to_canonical_entities(["TCP"], canonical_entities)
        self.assertTrue(len(m_tcp) >= 1)
        self.assertEqual(m_tcp[0].canonical_name, "Transmission Control Protocol")

        # 2. Adversarial: Query for TCP must NEVER match UDP (Disallowed merge pair)
        matched_keys = [e.entity_key for e in m_tcp]
        self.assertNotIn("concept:udp", matched_keys)

        # 3. Match Java in programming context
        m_java = match_query_to_canonical_entities(
            ["Java"], canonical_entities, raw_query="How does Java compile source code into bytecode?"
        )
        self.assertTrue(len(m_java) >= 1)
        self.assertEqual(m_java[0].canonical_name, "Java")

    def test_multi_source_evidence_aggregation(self):
        """Test retrieving and unifying evidence from printed PDF, handwritten notes, and research papers."""
        # Create Doc 1: Printed PDF
        doc1 = Document(
            user_id=self.user1.id,
            filename="networking_fundamentals.pdf",
            file_path="uploads/doc1.pdf",
            document_type="pdf",
            extracted_text="TCP is a reliable connection-oriented protocol.",
            text_length=50,
            is_handwritten=False,
        )
        # Create Doc 2: Handwritten Notes
        doc2 = Document(
            user_id=self.user1.id,
            filename="lecture_handwritten_notes.pdf",
            file_path="uploads/doc2.pdf",
            document_type="handwritten",
            extracted_text="Handshake flags: SYN and ACK initiate connection.",
            text_length=55,
            is_handwritten=True,
        )
        # Create Doc 3: Research Paper
        doc3 = Document(
            user_id=self.user1.id,
            filename="transport_paper.pdf",
            file_path="uploads/doc3.pdf",
            document_type="research_paper",
            extracted_text="Evaluation shows TCP throughput under congestion.",
            text_length=60,
            is_handwritten=False,
        )
        self.db.add_all([doc1, doc2, doc3])
        self.db.commit()
        self.db.refresh(doc1)
        self.db.refresh(doc2)
        self.db.refresh(doc3)

        # Add chunk for Doc 1
        chunk1 = DocumentChunk(
            document_id=doc1.id,
            chunk_index=0,
            page_number=3,
            content="TCP provides ordered delivery and error checking for packets.",
        )
        # Add HandwrittenPage for Doc 2
        hw_page = HandwrittenPage(
            document_id=doc2.id,
            page_number=1,
            original_image_path="uploads/hw1.png",
            raw_transcription="TCP uses a three-way handshake involving SYN and ACK flags.",
            confidence_score=0.91,
            status="completed",
        )
        # Add ResearchPaperAnalysis for Doc 3
        rpa = ResearchPaperAnalysis(
            document_id=doc3.id,
            user_id=self.user1.id,
            content_hash="hash123",
            analysis_version="phase1_v1",
            paper_detection={"is_research_paper": True},
            basic_information={"title": "Transport Paper"},
            research_context={},
            methodology={"summary": "We evaluate TCP performance in high-latency network topologies."},
            evaluation={"summary": "TCP achieved stable congestion control windows."},
            conclusion={},
            sections=[],
            numerical_data=[],
            tables_and_figures=[],
            evidence=[],
            timings={},
        )
        self.db.add_all([chunk1, hw_page, rpa])
        self.db.commit()

        target_entity = CanonicalEntityOut(
            entity_key="concept:tcp",
            canonical_name="TCP",
            normalized_name="tcp",
            entity_type="Protocol",
            importance_score=0.9,
            document_count=3,
            is_shared=True,
            occurrences=[
                # Occurrence from Doc 1
                {
                    "document_id": doc1.id,
                    "document_name": doc1.filename,
                    "page_number": 3,
                    "original_label": "TCP",
                    "source_text": "TCP is a reliable connection-oriented protocol.",
                    "resolution_confidence": 0.95,
                    "resolution_method": "exact_match",
                    "evidence": {},
                }
            ],
        )

        evidence = retrieve_multi_source_evidence(
            db=self.db,
            user_id=self.user1.id,
            documents=[doc1, doc2, doc3],
            target_entities=[target_entity],
            all_canonical_entities=[target_entity],
            edges=[],
            max_evidence_items=10,
        )

        self.assertTrue(len(evidence) >= 2)
        source_types = {ev.source_type for ev in evidence}
        # Verify multi-modal recognition
        self.assertTrue("printed_pdf" in source_types or "document_chunk" in source_types)
        self.assertIn("handwritten", source_types)
        self.assertIn("research_paper", source_types)

        # Verify exact page numbers preserved
        pages = {ev.page_number for ev in evidence}
        self.assertIn(1, pages)
        self.assertIn(3, pages)

    def test_conservative_conflict_and_difference_detection(self):
        """Test detecting true contradictions vs different emphases between documents."""
        doc1 = Document(
            user_id=self.user1.id,
            filename="protocol_guide.txt",
            document_type="txt",
            file_path="uploads/protocol_guide.txt",
            extracted_text="TCP is a connection-oriented protocol providing reliable transmission.",
        )
        doc2 = Document(
            user_id=self.user1.id,
            filename="alternative_notes.txt",
            document_type="txt",
            file_path="uploads/alternative_notes.txt",
            extracted_text="In this context, the protocol operates as connectionless and unreliable.",
        )
        self.db.add_all([doc1, doc2])
        self.db.commit()

        target_entity = CanonicalEntityOut(
            entity_key="concept:protocol",
            canonical_name="Protocol",
            normalized_name="protocol",
            is_shared=True,
            document_count=2,
            occurrences=[
                {"document_id": doc1.id, "document_name": doc1.filename, "page_number": 1, "original_label": "Protocol", "source_text": "TCP is a connection-oriented protocol providing reliable transmission."},
                {"document_id": doc2.id, "document_name": doc2.filename, "page_number": 1, "original_label": "Protocol", "source_text": "In this context, the protocol operates as connectionless and unreliable."},
            ],
        )

        evidence = retrieve_multi_source_evidence(
            db=self.db,
            user_id=self.user1.id,
            documents=[doc1, doc2],
            target_entities=[target_entity],
            all_canonical_entities=[target_entity],
            edges=[],
        )

        insights, conflicts = detect_cross_document_insights_and_conflicts(
            target_entities=[target_entity],
            all_canonical_entities=[target_entity],
            evidence=evidence,
            documents=[doc1, doc2],
        )

        # Must detect shared knowledge insight
        self.assertTrue(len(insights) >= 1)
        self.assertEqual(insights[0].insight_type, "shared_knowledge")

        # Must detect contradiction due to "connection-oriented" vs "connectionless"
        contradiction_conflicts = [c for c in conflicts if c.category == "contradiction"]
        self.assertTrue(len(contradiction_conflicts) >= 1)
        self.assertIn("Contradictory", contradiction_conflicts[0].description)

    def test_strict_grounded_answer_synthesis_and_insufficient_evidence(self):
        """Test grounded answer construction with valid sources and safe refusal when evidence is missing."""
        doc = Document(
            user_id=self.user1.id,
            filename="doc_sample.txt",
            document_type="txt",
            file_path="uploads/doc_sample.txt",
            extracted_text="Sample text",
        )
        self.db.add(doc)
        self.db.commit()

        # 1. When evidence is completely empty -> Insufficient Evidence
        empty_answer = synthesize_grounded_answer(
            query="What is quantum teleportation?",
            target_entities=[],
            evidence=[],
            insights=[],
            conflicts=[],
            selected_documents=[doc],
            skip_llm=True,
        )
        self.assertEqual(empty_answer.grounding_status, "insufficient_evidence")
        self.assertEqual(empty_answer.confidence, 0.0)
        self.assertIn("could not find", empty_answer.text.lower())

    def test_tenant_isolation_security(self):
        """Ensure User 2 CANNOT query or view User 1's documents or evidence."""
        # Create Doc owned by User 1
        doc_user1 = Document(
            user_id=self.user1.id,
            filename="confidential_user1_research.pdf",
            document_type="pdf",
            file_path="uploads/conf1.pdf",
            extracted_text="Secret algorithm details for User 1.",
            text_length=50,
        )
        self.db.add(doc_user1)
        self.db.commit()
        self.db.refresh(doc_user1)

        # User 2 attempts to query User 1's document -> 404 forbidden
        res = self.client.post(
            "/documents/knowledge-intelligence/query",
            json={
                "query": "What is the secret algorithm?",
                "document_ids": [doc_user1.id],
            },
            headers=self.headers_user2,
        )
        self.assertEqual(res.status_code, 404)

    def test_caching_and_invalidation(self):
        """Test query response caching, cache hits, force_refresh, and user cache clear."""
        doc = Document(
            user_id=self.user1.id,
            filename="cached_network_doc.txt",
            document_type="txt",
            file_path="uploads/cache_doc.txt",
            extracted_text="TCP establishes a three-way handshake with SYN and ACK flags.",
            text_length=60,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        req_payload = {
            "query": "What do my documents say about TCP?",
            "document_ids": [doc.id],
            "skip_llm": True,
            "force_refresh": False,
        }

        # 1. First execution: Cache miss
        res1 = self.client.post(
            "/documents/knowledge-intelligence/query",
            json=req_payload,
            headers=self.headers_user1,
        )
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertFalse(data1["cached"])

        # Verify entry in cache table
        cache_row = (
            self.db.query(KnowledgeIntelligenceCache)
            .filter(KnowledgeIntelligenceCache.user_id == self.user1.id)
            .first()
        )
        self.assertIsNotNone(cache_row)

        # 2. Second execution: Cache hit
        res2 = self.client.post(
            "/documents/knowledge-intelligence/query",
            json=req_payload,
            headers=self.headers_user1,
        )
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertTrue(data2["cached"])

        # 3. Third execution: force_refresh=True bypasses cache
        req_refresh = dict(req_payload)
        req_refresh["force_refresh"] = True
        res3 = self.client.post(
            "/documents/knowledge-intelligence/query",
            json=req_refresh,
            headers=self.headers_user1,
        )
        self.assertEqual(res3.status_code, 200)
        data3 = res3.json()
        self.assertFalse(data3["cached"])

        # 4. Clear cache endpoint
        res_del = self.client.delete(
            "/documents/knowledge-intelligence/cache",
            headers=self.headers_user1,
        )
        self.assertEqual(res_del.status_code, 200)
        del_data = res_del.json()
        self.assertEqual(del_data["status"], "success")

        # Verify cache table is now empty for User 1
        count_after = (
            self.db.query(KnowledgeIntelligenceCache)
            .filter(KnowledgeIntelligenceCache.user_id == self.user1.id)
            .count()
        )
        self.assertEqual(count_after, 0)

    def test_adversarial_queries(self):
        """Test adversarial inputs: polysemous words, disallowed pairs, and unknown topics."""
        doc = Document(
            user_id=self.user1.id,
            filename="adversarial_test_doc.txt",
            document_type="txt",
            file_path="uploads/adv.txt",
            extracted_text="The TCP protocol is used for web traffic. UDP is used for streaming.",
            text_length=70,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        # 1. Query for TCP
        res_tcp = self.client.post(
            "/documents/knowledge-intelligence/query",
            json={
                "query": "What is TCP?",
                "document_ids": [doc.id],
                "skip_llm": True,
            },
            headers=self.headers_user1,
        )
        self.assertEqual(res_tcp.status_code, 200)
        data_tcp = res_tcp.json()
        # Must focus on TCP and not conflate with UDP
        self.assertTrue(any("TCP" in ent for ent in data_tcp["focus_entities"]))
        self.assertFalse(any("UDP" in ent for ent in data_tcp["focus_entities"]))

        # 2. Query for completely non-existent topic
        res_none = self.client.post(
            "/documents/knowledge-intelligence/query",
            json={
                "query": "Explain everything about Quantum Holographic Gravitation",
                "document_ids": [doc.id],
                "skip_llm": True,
            },
            headers=self.headers_user1,
        )
        self.assertEqual(res_none.status_code, 200)
        data_none = res_none.json()
        self.assertEqual(data_none["direct_answer"]["grounding_status"], "insufficient_evidence")

    def test_entity_drilldown_endpoint(self):
        """Test GET /documents/knowledge-intelligence/entity/{entity_key} drilldown."""
        doc = Document(
            user_id=self.user1.id,
            filename="drilldown_doc.txt",
            document_type="txt",
            file_path="uploads/drilldown.txt",
            extracted_text="Convolutional Neural Networks are widely used for computer vision and image classification.",
            text_length=80,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        res = self.client.get(
            f"/documents/knowledge-intelligence/entity/concept:neural_networks?document_ids={doc.id}",
            headers=self.headers_user1,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("direct_answer", data)
        self.assertEqual(data["selected_document_ids"], [doc.id])

    def test_adversarial_polysemy_disambiguation(self):
        """Test disambiguating polysemous concepts such as Java programming vs Java island."""
        doc_island = Document(
            user_id=self.user1.id,
            filename="indonesia_geography.txt",
            document_type="txt",
            file_path="uploads/island.txt",
            extracted_text="Java is an island of Indonesia with volcanic mountains and Jakarta province.",
            text_length=75,
        )
        self.db.add(doc_island)
        self.db.commit()
        self.db.refresh(doc_island)

        # Query asking specifically about Java programming on the island document
        res = self.client.post(
            "/documents/knowledge-intelligence/query",
            json={
                "query": "How does Java compiler produce JVM bytecode in software development?",
                "document_ids": [doc_island.id],
                "skip_llm": True,
            },
            headers=self.headers_user1,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        # Java geography document should NOT claim to answer Java JVM programming questions
        self.assertEqual(data["direct_answer"]["grounding_status"], "insufficient_evidence")


if __name__ == "__main__":
    unittest.main()
