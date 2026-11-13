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
from app.models.user import User
from app.services.cross_document_entity_resolution import (
    ConceptCandidate,
    EntityResolutionPipeline,
    build_candidate_index,
    extract_acronym_candidates,
    is_acronym_match,
    normalize_concept_label,
)
from app.services.cross_document_graph_service import (
    compute_collection_hash,
    get_or_generate_cross_document_graph,
)


class CrossDocumentKnowledgeGraphTests(unittest.TestCase):
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
        self.db.query(EntityOccurrence).delete()
        self.db.query(CrossDocumentEdge).delete()
        self.db.query(CanonicalEntity).delete()
        self.db.query(CrossDocumentKnowledgeGraph).delete()
        self.db.query(KnowledgeGraphEdge).delete()
        self.db.query(KnowledgeGraphNode).delete()
        self.db.query(KnowledgeGraph).delete()
        self.db.query(DocumentChunk).delete()
        self.db.query(Document).delete()
        self.db.query(User).delete()
        self.db.commit()

        # Seed User 1
        self.user1 = User(
            email="researcher1@cognidocs.ai",
            password_hash=hash_password("password123"),
            full_name="Researcher One",
            is_verified=True,
        )
        # Seed User 2 (for tenant isolation tests)
        self.user2 = User(
            email="attacker2@cognidocs.ai",
            password_hash=hash_password("password123"),
            full_name="User Two",
            is_verified=True,
        )
        self.db.add_all([self.user1, self.user2])
        self.db.commit()
        self.db.refresh(self.user1)
        self.db.refresh(self.user2)

        self.token1 = create_access_token({"sub": str(self.user1.id)})
        self.token2 = create_access_token({"sub": str(self.user2.id)})
        self.headers1 = {"Authorization": f"Bearer {self.token1}"}
        self.headers2 = {"Authorization": f"Bearer {self.token2}"}

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        # Seed Document A (Handwritten networking notes)
        full_text_a = (
            "TCP Three-Way Handshake establishes reliable connections between client and server. "
            "SYN Flood is an attack that exploits TCP by flooding SYN packets without returning ACK. "
            "Transmission Control Block (TCB) holds state for each active TCP connection. "
            "SYN Cookies defends against SYN Flood by delaying TCB allocation."
        )
        self.doc_a = Document(
            user_id=self.user1.id,
            filename="networking_notes.pdf",
            document_type="PDF",
            file_path="uploads/networking_notes.pdf",
            extracted_text=full_text_a,
            text_length=len(full_text_a),
            is_handwritten=True,
            processing_status="completed",
            processing_progress=100,
        )

        # Seed Document B (Academic research paper)
        full_text_b = (
            "In high-throughput cloud environments, Transmission Control Protocol (TCP) governs packet transport. "
            "Homomorphic Encryption protects sensitive payload data in transit across TCP streams. "
            "Cloud Security architectures evaluate encryption overhead against network bandwidth. "
            "Transmission Control Protocol implementations mitigate Denial of Service vectors."
        )
        self.doc_b = Document(
            user_id=self.user1.id,
            filename="cloud_security_paper.pdf",
            document_type="PDF",
            file_path="uploads/cloud_security_paper.pdf",
            extracted_text=full_text_b,
            text_length=len(full_text_b),
            is_handwritten=False,
            processing_status="completed",
            processing_progress=100,
        )
        self.db.add_all([self.doc_a, self.doc_b])
        self.db.commit()
        self.db.refresh(self.doc_a)
        self.db.refresh(self.doc_b)

        # Chunks for Doc A
        chunk_a1 = DocumentChunk(
            document_id=self.doc_a.id,
            chunk_index=0,
            page_number=1,
            content=(
                "TCP Three-Way Handshake establishes reliable connections between client and server. "
                "SYN Flood is an attack that exploits TCP by flooding SYN packets without returning ACK."
            ),
        )
        chunk_a2 = DocumentChunk(
            document_id=self.doc_a.id,
            chunk_index=1,
            page_number=2,
            content=(
                "Transmission Control Block (TCB) holds state for each active TCP connection. "
                "SYN Cookies defends against SYN Flood by delaying TCB allocation."
            ),
        )
        # Chunks for Doc B
        chunk_b1 = DocumentChunk(
            document_id=self.doc_b.id,
            chunk_index=0,
            page_number=1,
            content=(
                "In high-throughput cloud environments, Transmission Control Protocol (TCP) governs packet transport. "
                "Homomorphic Encryption protects sensitive payload data in transit across TCP streams."
            ),
        )
        chunk_b2 = DocumentChunk(
            document_id=self.doc_b.id,
            chunk_index=1,
            page_number=2,
            content=(
                "Cloud Security architectures evaluate encryption overhead against network bandwidth. "
                "Transmission Control Protocol implementations mitigate Denial of Service vectors."
            ),
        )
        self.db.add_all([chunk_a1, chunk_a2, chunk_b1, chunk_b2])
        self.db.commit()

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    def test_01_normalization_and_acronym_candidates(self):
        """Verify normalization preserves core concepts and correctly identifies parenthetical definitions."""
        norm1 = normalize_concept_label("Transmission Control Protocol (TCP)")
        self.assertEqual(norm1, "transmission control protocol")

        norm2 = normalize_concept_label("  SYN-Flood / Attack!  ")
        self.assertEqual(norm2, "syn flood attack")

        # Acronym extractions
        acrs = extract_acronym_candidates("Transmission Control Protocol (TCP)")
        self.assertIn("TCP", acrs)

        acrs_ai = extract_acronym_candidates("Artificial Intelligence")
        self.assertIn("AI", acrs_ai)

        acrs_dek = extract_acronym_candidates("Data Encryption Key")
        self.assertIn("DEK", acrs_dek)

    def test_02_acronym_match_and_equivalence_suffix(self):
        """Verify acronyms and formal suffixes unify without LLM dependence."""
        self.assertTrue(is_acronym_match("TCP", "Transmission Control Protocol"))
        self.assertTrue(is_acronym_match("Transmission Control Protocol", "TCP"))
        self.assertTrue(is_acronym_match("AI", "Artificial Intelligence"))
        self.assertTrue(is_acronym_match("TCB", "Transmission Control Block"))

        pipeline = EntityResolutionPipeline(skip_llm=True)
        cand_short = ConceptCandidate(
            document_id=1,
            document_name="Doc1",
            node_key="k1",
            label="Python",
            normalized_label="python",
            node_type="Concept",
            aliases=[],
            description=None,
            importance_score=0.8,
            confidence=0.85,
            evidence=[],
            source_pages=[1],
            context_excerpt="Python is an interpreted programming language.",
        )
        cand_long = ConceptCandidate(
            document_id=2,
            document_name="Doc2",
            node_key="k2",
            label="Python programming language",
            normalized_label="python programming language",
            node_type="Concept",
            aliases=[],
            description=None,
            importance_score=0.85,
            confidence=0.9,
            evidence=[],
            source_pages=[1],
            context_excerpt="The Python programming language is widely used for software development.",
        )
        decision = pipeline.evaluate_pair(cand_short, cand_long)
        self.assertTrue(decision.same_entity)
        self.assertEqual(decision.method, "lexical_equivalence")
        self.assertGreaterEqual(decision.confidence, 0.75)

    def test_03_false_merge_adversarial_rejection(self):
        """Verify adversarial pairs (Java polysemy, TCP vs UDP, SYN vs SYN Flood) are strictly rejected."""
        pipeline = EntityResolutionPipeline(skip_llm=True)

        # Case A: Java programming language vs Java island in Indonesia
        cand_java_prog = ConceptCandidate(
            document_id=1,
            document_name="DocA",
            node_key="j1",
            label="Java",
            normalized_label="java",
            node_type="Concept",
            aliases=[],
            description=None,
            importance_score=0.8,
            confidence=0.8,
            evidence=[],
            source_pages=[1],
            context_excerpt="Java bytecode executes on the Java Virtual Machine (JVM) runtime with garbage collection.",
        )
        cand_java_island = ConceptCandidate(
            document_id=2,
            document_name="DocB",
            node_key="j2",
            label="Java",
            normalized_label="java",
            node_type="Concept",
            aliases=[],
            description=None,
            importance_score=0.8,
            confidence=0.8,
            evidence=[],
            source_pages=[1],
            context_excerpt="Java is an Indonesian island with the capital Jakarta, famous for volcanoes and coffee plantations.",
        )
        decision_java = pipeline.evaluate_pair(cand_java_prog, cand_java_island)
        self.assertFalse(decision_java.same_entity, "Polysemous Java across divergent domains must NOT merge!")
        self.assertEqual(decision_java.method, "context_disambiguation")

        # Case B: TCP vs UDP (distinct network protocols)
        cand_tcp = ConceptCandidate(
            document_id=1, document_name="DocA", node_key="t", label="TCP", normalized_label="tcp",
            node_type="Protocol", aliases=[], description=None, importance_score=0.9, confidence=0.9,
            evidence=[], source_pages=[1], context_excerpt="TCP protocol packet transmission.",
        )
        cand_udp = ConceptCandidate(
            document_id=2, document_name="DocB", node_key="u", label="UDP", normalized_label="udp",
            node_type="Protocol", aliases=[], description=None, importance_score=0.9, confidence=0.9,
            evidence=[], source_pages=[1], context_excerpt="UDP datagram transmission.",
        )
        decision_udp = pipeline.evaluate_pair(cand_tcp, cand_udp)
        self.assertFalse(decision_udp.same_entity, "TCP and UDP must never merge!")

        # Case C: SYN vs SYN Flood (control flag vs attack)
        cand_syn = ConceptCandidate(
            document_id=1, document_name="DocA", node_key="s", label="SYN", normalized_label="syn",
            node_type="Concept", aliases=[], description=None, importance_score=0.7, confidence=0.8,
            evidence=[], source_pages=[1], context_excerpt="The client sends a SYN packet to initiate connection.",
        )
        cand_syn_flood = ConceptCandidate(
            document_id=2, document_name="DocB", node_key="sf", label="SYN Flood", normalized_label="syn flood",
            node_type="Attack", aliases=[], description=None, importance_score=0.9, confidence=0.9,
            evidence=[], source_pages=[1], context_excerpt="SYN Flood is a distributed attack that exhausts backlog memory.",
        )
        decision_syn_flood = pipeline.evaluate_pair(cand_syn, cand_syn_flood)
        self.assertFalse(decision_syn_flood.same_entity, "SYN and SYN Flood must never merge!")

        # Case D: Client vs Server
        cand_client = ConceptCandidate(
            document_id=1, document_name="DocA", node_key="c", label="Client", normalized_label="client",
            node_type="Entity", aliases=[], description=None, importance_score=0.6, confidence=0.7,
            evidence=[], source_pages=[1], context_excerpt="The client sends the request.",
        )
        cand_server = ConceptCandidate(
            document_id=2, document_name="DocB", node_key="srv", label="Server", normalized_label="server",
            node_type="Entity", aliases=[], description=None, importance_score=0.6, confidence=0.7,
            evidence=[], source_pages=[1], context_excerpt="The server listens on port 80.",
        )
        decision_client_server = pipeline.evaluate_pair(cand_client, cand_server)
        self.assertFalse(decision_client_server.same_entity, "Client and Server must never merge!")

    def test_04_bounded_candidate_indexing_and_pruning(self):
        """Verify candidate inverted index bounds comparisons to sharing terms only."""
        candidates = [
            ConceptCandidate(1, "D1", "k1", "TCP", "tcp", "Protocol", [], None, 0.8, 0.8, [], [1]),
            ConceptCandidate(2, "D2", "k2", "Transmission Control Protocol", "transmission control protocol", "Protocol", [], None, 0.8, 0.8, [], [1]),
            ConceptCandidate(1, "D1", "k3", "Quantum Computing", "quantum computing", "Concept", [], None, 0.8, 0.8, [], [1]),
            ConceptCandidate(2, "D2", "k4", "Qubit", "qubit", "Concept", [], None, 0.8, 0.8, [], [1]),
            ConceptCandidate(3, "D3", "k5", "Photosynthesis", "photosynthesis", "Concept", [], None, 0.8, 0.8, [], [1]),
        ]
        index = build_candidate_index(candidates)
        # Acronym key 'acr:tcp' must link index 0 and index 1
        self.assertIn("acr:tcp", index)
        self.assertIn(0, index["acr:tcp"])
        self.assertIn(1, index["acr:tcp"])

        # 'photosynthesis' must not share an index key with 'tcp'
        photo_keys = [k for k, v in index.items() if 4 in v]
        for k in photo_keys:
            self.assertNotIn(0, index[k])

    def test_05_deterministic_cache_fingerprint(self):
        """Verify cache collection hash is order-independent and invalidates on content change."""
        hashes = {1: "hash_a", 2: "hash_b", 3: "hash_c"}
        hash_order_1 = compute_collection_hash(user_id=42, document_ids=[1, 2, 3], doc_hashes=hashes)
        hash_order_2 = compute_collection_hash(user_id=42, document_ids=[3, 1, 2], doc_hashes=hashes)
        self.assertEqual(hash_order_1, hash_order_2, "Document ID order must not affect collection hash!")

        # Change document selection
        hash_different_docs = compute_collection_hash(user_id=42, document_ids=[1, 2], doc_hashes=hashes)
        self.assertNotEqual(hash_order_1, hash_different_docs)

        # Change document content
        changed_hashes = {1: "hash_a_modified", 2: "hash_b", 3: "hash_c"}
        hash_modified_content = compute_collection_hash(user_id=42, document_ids=[1, 2, 3], doc_hashes=changed_hashes)
        self.assertNotEqual(hash_order_1, hash_modified_content)

        # Change user
        hash_other_user = compute_collection_hash(user_id=99, document_ids=[1, 2, 3], doc_hashes=hashes)
        self.assertNotEqual(hash_order_1, hash_other_user)

    def test_06_end_to_end_cross_document_graph_generation(self):
        """Verify cross-document graph generation unifies shared concepts while retaining document provenance."""
        res = get_or_generate_cross_document_graph(
            db=self.db,
            user_id=self.user1.id,
            document_ids=[self.doc_a.id, self.doc_b.id],
            force_refresh=True,
            include_low_confidence=True,
            skip_llm=True,
        )
        self.assertIsNotNone(res.id)
        self.assertEqual(len(res.selected_document_ids), 2)
        self.assertGreater(len(res.entities), 0)

        # Check for shared entity 'TCP' / 'Transmission Control Protocol'
        tcp_entity = next(
            (e for e in res.entities if "tcp" in e.normalized_name or "transmission control protocol" in e.normalized_name),
            None,
        )
        self.assertIsNotNone(tcp_entity, "TCP must be extracted and resolved!")
        self.assertTrue(tcp_entity.is_shared, "TCP appears in both Doc A and Doc B, so is_shared must be True!")
        self.assertEqual(tcp_entity.document_count, 2)
        self.assertGreaterEqual(tcp_entity.occurrence_count, 2)

        # Verify exact document provenance in occurrences
        doc_ids_in_occurrences = {occ.document_id for occ in tcp_entity.occurrences}
        self.assertIn(self.doc_a.id, doc_ids_in_occurrences)
        self.assertIn(self.doc_b.id, doc_ids_in_occurrences)

        for occ in tcp_entity.occurrences:
            self.assertIsNotNone(occ.source_text)
            self.assertGreater(len(occ.source_text), 0)
            self.assertGreaterEqual(occ.page_number, 1)

        # Verify document-specific concept
        syn_flood_ent = next(
            (e for e in res.entities if "syn flood" in e.normalized_name),
            None,
        )
        if syn_flood_ent:
            self.assertFalse(syn_flood_ent.is_shared, "SYN Flood only appears in Doc A, so is_shared must be False!")
            self.assertEqual(syn_flood_ent.document_count, 1)

    def test_07_strict_user_ownership_and_tenant_isolation(self):
        """Verify User 2 cannot access or generate graphs using User 1's documents."""
        # Attempt to generate graph with User 1's documents under User 2 auth
        response = self.client.post(
            "/documents/knowledge-graph/cross-document",
            headers=self.headers2,
            json={"document_ids": [self.doc_a.id, self.doc_b.id]},
        )
        self.assertEqual(response.status_code, 404, "User 2 must receive 404 when selecting User 1's documents!")

        # Generate valid graph for User 1
        res1 = self.client.post(
            "/documents/knowledge-graph/cross-document",
            headers=self.headers1,
            json={"document_ids": [self.doc_a.id, self.doc_b.id]},
        )
        self.assertEqual(res1.status_code, 200)
        graph_id = res1.json()["id"]

        # Attempt to fetch User 1's graph with User 2 auth
        res_unauthorized = self.client.get(
            f"/documents/knowledge-graph/cross-document/{graph_id}",
            headers=self.headers2,
        )
        self.assertEqual(res_unauthorized.status_code, 404, "User 2 cannot fetch User 1's cross-doc graph!")

    def test_08_atomic_replacement_and_concurrency(self):
        """Verify rapid repeated regeneration replaces graph cleanly without orphan rows."""
        for _ in range(3):
            res = get_or_generate_cross_document_graph(
                db=self.db,
                user_id=self.user1.id,
                document_ids=[self.doc_a.id, self.doc_b.id],
                force_refresh=True,
                include_low_confidence=True,
                skip_llm=True,
            )
            self.assertIsNotNone(res.id)

        # Check total count of cross-document graphs in DB for this user
        graphs_in_db = (
            self.db.query(CrossDocumentKnowledgeGraph)
            .filter(CrossDocumentKnowledgeGraph.user_id == self.user1.id)
            .count()
        )
        self.assertEqual(graphs_in_db, 1, "There must be exactly 1 active graph for this user and collection!")

    def test_09_api_endpoints_via_testclient(self):
        """Verify all Phase 2 REST API endpoints return compliant schemas."""
        # POST generate
        post_res = self.client.post(
            "/documents/knowledge-graph/cross-document",
            headers=self.headers1,
            json={"document_ids": [self.doc_a.id, self.doc_b.id], "force_refresh": True},
        )
        self.assertEqual(post_res.status_code, 200)
        data = post_res.json()
        graph_id = data["id"]
        self.assertEqual(data["cached"], False)
        self.assertGreater(len(data["entities"]), 0)

        # GET by ID (should be cached)
        get_res = self.client.get(
            f"/documents/knowledge-graph/cross-document/{graph_id}",
            headers=self.headers1,
        )
        self.assertEqual(get_res.status_code, 200)
        get_data = get_res.json()
        self.assertEqual(get_data["cached"], True)

        # GET entities list
        ents_res = self.client.get(
            f"/documents/knowledge-graph/cross-document/{graph_id}/entities",
            headers=self.headers1,
        )
        self.assertEqual(ents_res.status_code, 200)
        ents_data = ents_res.json()
        self.assertIsInstance(ents_data, list)
        self.assertGreater(len(ents_data), 0)

        # GET single entity detail
        first_key = ents_data[0]["entity_key"]
        single_ent_res = self.client.get(
            f"/documents/knowledge-graph/cross-document/{graph_id}/entity/{first_key}",
            headers=self.headers1,
        )
        self.assertEqual(single_ent_res.status_code, 200)
        self.assertEqual(single_ent_res.json()["entity_key"], first_key)

        # GET evidence list
        ev_res = self.client.get(
            f"/documents/knowledge-graph/cross-document/{graph_id}/evidence",
            headers=self.headers1,
        )
        self.assertEqual(ev_res.status_code, 200)
        self.assertIsInstance(ev_res.json(), list)

        # DELETE
        del_res = self.client.delete(
            f"/documents/knowledge-graph/cross-document/{graph_id}",
            headers=self.headers1,
        )
        self.assertEqual(del_res.status_code, 200)
        self.assertTrue(del_res.json()["deleted"])


if __name__ == "__main__":
    unittest.main()

