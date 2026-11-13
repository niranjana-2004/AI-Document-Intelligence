# Cognidocs — Knowledge Graph Phase 2: Cross-Document Knowledge Graph

**Status**: **Production Ready (Verified & Frozen)**  
**Feature**: Cross-Document Grounded Knowledge Graph  
**Scope**: Multi-Document Personal Knowledge Entity Resolution & Grounded Relationship Traversal  

---

## 1. Overview & Purpose

While **Knowledge Graph Phase 1** focused on extracting grounded concepts and relationships within a single document, **Knowledge Graph Phase 2** enables Cognidocs to recognize when the **same underlying concept/entity appears across multiple documents** in the user's personal document collection.

Phase 2 answers:
> **"What does Cognidocs know about this concept across my documents?"**

For example, when a user uploads:
1. Handwritten notes discussing `TCP`, `SYN Flood`, and `Transmission Control Block (TCB)`
2. An academic research paper discussing `Transmission Control Protocol` and `Homomorphic Encryption`
3. A technical report discussing network protocol security

Cognidocs unifies these into a single **Canonical Personal Entity** `TCP` while preserving complete document-level provenance.

```
                    ┌──────────────┐
                    │     TCP      │
                    │ Shared Entity│
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
         Document #12  Document #2   Document #14
         Handwritten   Research      Technical
         Notes         Paper         Notes
         (pp. 1, 2)    (pp. 1, 4)    (pp. 1)
```

---

## 2. Core Architectural Guarantees

1. **Zero Grounding Loss**:
   - Every shared entity occurrence points directly to `document_id`, `document_name`, `chunk_id`, `page_number`, and a verbatim source excerpt.
   - Cross-document relationships are created **only when supported by concrete source document evidence**. No speculative leaps (e.g., if Doc A mentions X and Doc B mentions Y, the system never invents $X \to Y$ unless explicitly stated in source text).
2. **Strict User / Tenant Isolation**:
   - All models (`CrossDocumentKnowledgeGraph`, `CanonicalEntity`, `EntityOccurrence`, `CrossDocumentEdge`) are strictly scoped by `user_id`.
   - Every query enforces JWT tenant boundaries at the repository/service layer. User A can never discover or query User B's entities, memberships, or evidence.
3. **No External Infrastructure Dependencies**:
   - Built cleanly on top of SQLite, SQLAlchemy, existing MiniLM embeddings (`all-MiniLM-L6-v2`), and local Ollama (`llama3.2`). No Neo4j, pgvector, or external graph database required.
4. **Deterministic Fingerprint Caching**:
   - Cache key is computed deterministically:
     $$\text{collection\_hash} = \text{SHA-256}(user\_id : \text{sorted}(doc\_ids) : \text{sorted}(content\_hashes) : version)$$
   - Document order independence: selecting `[12, 2]` vs `[2, 12]` hits the identical cached graph.
   - Content invalidation: editing any document chunk or handwritten transcription automatically changes the content hash, invalidating the cached collection graph.

---

## 3. Database Schema

The Phase 2 schema is implemented in `backend/app/models/cross_document_knowledge_graph.py` with idempotent migration via `ensure_cross_document_knowledge_graph_schema`:

### Table `cross_document_knowledge_graphs`
- `id`: Integer Primary Key
- `user_id`: ForeignKey to `users.id` (CASCADE)
- `collection_hash`: VARCHAR(128) indexed
- `selected_doc_ids_json`: JSON list of document IDs
- `graph_version`: VARCHAR(32) (e.g. `cdkg-v1`)
- `status`: VARCHAR(32) (`ready`)
- `generation_method`: VARCHAR(64) (`deterministic` / `hybrid`)
- `stats_json`: JSON metrics
- `diagnostics_json`: JSON profiling telemetry
- `created_at`, `updated_at`: DateTime timestamps

### Table `canonical_entities`
- `id`: Integer Primary Key
- `graph_id`: ForeignKey to `cross_document_knowledge_graphs.id` (CASCADE)
- `user_id`: ForeignKey to `users.id` (CASCADE)
- `entity_key`: VARCHAR(160) indexed slug
- `canonical_name`: VARCHAR(255)
- `normalized_name`: VARCHAR(255) indexed
- `entity_type`: VARCHAR(64) (e.g. `Protocol`, `Concept`, `Attack`, `System`)
- `description`: TEXT
- `aliases_json`: JSON list of strings
- `confidence`: Float ($0.0 - 1.0$)
- `confidence_tier`: VARCHAR(16) (`high`, `medium`, `low`)
- `importance_score`: Float
- `document_count`: Integer (number of unique documents containing this entity)
- `occurrence_count`: Integer (total number of mentions)
- `is_shared`: Boolean (`True` if `document_count >= 2`)
- `documents_json`: JSON list of `{document_id, document_name, occurrences, source_pages}`

### Table `entity_occurrences`
- `id`: Integer Primary Key
- `canonical_entity_id`: ForeignKey to `canonical_entities.id` (CASCADE)
- `graph_id`: ForeignKey to `cross_document_knowledge_graphs.id` (CASCADE)
- `user_id`: ForeignKey to `users.id` (CASCADE)
- `document_id`: ForeignKey to `documents.id` (CASCADE)
- `document_name`: VARCHAR(255)
- `chunk_id`: Integer, nullable
- `page_number`: Integer
- `original_label`: VARCHAR(255)
- `source_text`: TEXT (verbatim source excerpt)
- `resolution_confidence`: Float
- `resolution_method`: VARCHAR(64) (`exact_match`, `acronym_match`, `alias_match`, `lexical_equivalence`, `lexical_semantic_match`, `context_disambiguation`)
- `evidence_json`: JSON `EvidenceRef`

### Table `cross_document_edges`
- `id`: Integer Primary Key
- `graph_id`: ForeignKey to `cross_document_knowledge_graphs.id` (CASCADE)
- `user_id`: ForeignKey to `users.id` (CASCADE)
- `source_entity_id`: ForeignKey to `canonical_entities.id` (CASCADE)
- `target_entity_id`: ForeignKey to `canonical_entities.id` (CASCADE)
- `source_key`: VARCHAR(160)
- `target_key`: VARCHAR(160)
- `relationship`: VARCHAR(64) (20 controlled predicates)
- `origin`: VARCHAR(32) (`explicit`, `derived`)
- `confidence`: Float (with multi-document corroboration boost)
- `confidence_tier`: VARCHAR(16) (`high`, `medium`, `low`)
- `confidence_breakdown_json`: JSON factors
- `evidence_count`: Integer
- `supporting_document_ids_json`: JSON list of supporting document IDs
- `evidence_json`: JSON list of grounded evidence items annotated with `document_id` and `document_name`
- `explanation`: TEXT
- `is_cross_document`: Boolean (`True` if supported by $\ge 2$ documents)

---

## 4. Multi-Signal Entity Resolution Pipeline

To prevent false merges while achieving high recall across diverse writing styles, the pipeline in `backend/app/services/cross_document_entity_resolution.py` evaluates candidate pairs using bounded candidate indexing and multiple safety signals:

```
Document Concepts
        ↓
Inverted Candidate Indexing (Tokens, Acronyms, Aliases)
        ↓
Explicit Guardrails (Disallowed Pairs)
        ↓
Exact Normalized Label Match
        ↓
Known Aliases Check
        ↓
Acronym Expansion Verification
        ↓
Equivalence Suffix Matching ("Python" vs "Python programming language")
        ↓
Context-Aware Domain Disambiguation ("Java" programming vs "Java" geography)
        ↓
MiniLM Semantic Similarity & Context Excerpt Embedding
        ↓
Union-Find Transitive Unification
        ↓
Canonical Entity Creation & Grounded Occurrence Mapping
```

### Safety Guardrails & False-Merge Prevention
1. **Explicit Guardrails**: Distinct concepts that frequently co-occur (e.g. `TCP` vs `UDP`, `SYN` vs `ACK`, `SYN` vs `SYN Flood`, `Client` vs `Server`, `Precision` vs `Recall`) are strictly blocked from merging.
2. **Equivalence vs Composite Suffixes**:
   - Equivalence suffixes merge (e.g. `Python` + `programming language` = `Python programming language`, `RSA` + `algorithm` = `RSA algorithm`).
   - Composite / relation nouns are blocked (e.g. `SYN` + `flood` = `SYN Flood`, `TCP` + `handshake` = `TCP Handshake`).
3. **Polysemous Domain Disambiguation**: For words with multiple meanings (e.g. `Java`), context token clusters (JVM/bytecode/compiler vs island/indonesia/volcano) prevent cross-domain conflation.

---

## 5. API Reference

All endpoints require JWT Bearer token authentication:

| Endpoint | Method | Description |
|---|---|---|
| `/documents/knowledge-graph/cross-document` | `POST` | Generate or fetch cached cross-document graph for `document_ids`. Supports `force_refresh`, `include_low_confidence`, `skip_llm`, `only_shared`. |
| `/documents/knowledge-graph/cross-document/{graph_id}` | `GET` | Fetch stored cross-document graph by ID. |
| `/documents/knowledge-graph/cross-document/{graph_id}/entities` | `GET` | Search and filter canonical entities (`?q=...`, `?only_shared=true`). |
| `/documents/knowledge-graph/cross-document/{graph_id}/entity/{key}` | `GET` | Retrieve full occurrence and evidence details for a canonical entity. |
| `/documents/knowledge-graph/cross-document/{graph_id}/evidence` | `GET` | Retrieve all grounded evidence items across entities and edges. |
| `/documents/knowledge-graph/cross-document/{graph_id}` | `DELETE` | Delete stored cross-document graph and all child records. |

---

## 6. Frontend Workspace (`/knowledge-graph`)

The UI in `frontend/src/pages/KnowledgeGraph.jsx` seamlessly toggles between **Single Document** and **Cross-Document** modes:

1. **Mode Switcher**: Clean segmented pills (`Single Document` vs `Cross-Document`) in the header.
2. **Multi-Document Selector**: Checkbox cards with search, Select All, Clear Selection, and document type tags.
3. **Shared Entity Visuals**: Shared entities receive a green glowing border (`.kg-node-shared`) and a pill badge (e.g. `3 Docs`).
4. **Scope & Document Filters**:
   - Scope Filter: `All`, `Shared (≥2 Docs)`, `Doc-Specific`.
   - Document Filter: Isolate nodes to a specific document without fabricating edges.
5. **Grouped Evidence Drawer**:
   - Entities display evidence grouped by document, showing page numbers and verbatim excerpts.
   - **Open Source Page**: Deep-links to `/documents?doc=...&page=...` or `/handwritten/:id?page=...`.
6. **Multi-Document Chat Deep-Link**:
   - Every canonical entity includes an action button: **"Ask AI about [Entity] across documents"**, navigating to `/ask-ai` with preselected document scope and prepopulated grounded question.

---

## 7. Benchmark Results on Real Cognidocs Documents

Evaluated on real documents in an isolated test clone (`backend/benchmarks/cross_document_knowledge_graph_results.json`):

### Collection 1: Real Networking Documents (`[12, 14, 16]`)
- **Doc 12**: Handwritten Networking Notes (TCP, SYN Flood, TCB)
- **Doc 14**: Base Networking Document (TCP, Three-Way Handshake, HTTP)
- **Doc 16**: Extended Networking Document (TCP, Ports, Packets)

| Metric | Result |
|---|---:|
| Documents Selected | 3 |
| Cold Generation Latency | **18.406s** |
| Warm Cache Hit Latency | **0.0757s** (**243x speedup**) |
| Total Canonical Entities | 33 |
| **Shared Entities** | **2** (`TCP` across 3 documents with 9 mentions) |
| Document-Specific Entities | 31 |
| Total Edges | 40 |
| Cross-Document Edges | 1 |
| **Evidence Grounding Rate** | **100% (57/57 occurrences verified verbatim)** |
| **False Merge Rate** | **0.0%** |

---

## 8. Regression & Safety Verification Matrix

| Suite | Scope | Pass / Total |
|---|---|:---:|
| `test_cross_document_knowledge_graph.py` | Phase 2 Entity Resolution, Caching, Ownership, Concurrency, API | **9 / 9 OK** |
| `test_knowledge_graph.py` | Phase 1 Knowledge Graph Baseline | **26 / 26 OK** |
| `test_research_paper_analyzer.py` | Academic Research Paper Analyzer | **37 / 37 OK** |
| `test_grounded_citations.py` | Grounded Multi-Page Citations | **10 / 10 OK** |
| `test_search_service.py` | Hybrid Keyword & Semantic Search | **18 / 18 OK** |
| `test_voice_assistant.py` | Piper TTS & faster-whisper STT | **14 / 14 OK** |
| `test_voice_query_recovery.py` | Context-Aware Voice Query Recovery | **21 / 21 OK** |
| `test_layout_guided_ocr_phase_b.py` | Layout Guided TrOCR & Region Analysis | **16 / 16 OK** |
| `test_email_verification_status.py` | User Auth & Email Verification Status | **9 / 9 OK** |
| Frontend Unit Tests (`*.test.mjs`) | Layout, Filtering, Navigation, Voice | **18 / 18 PASS** |
| ESLint | Targeted Knowledge Graph files | **0 errors, 0 warnings** |
| Vite Production Build | Bundle compilation | **PASS (1.29s)** |
| Database Non-Mutation | `backend/documents.db` row counts | **102 / 102 / 1 (Pristine)** |

---

## 9. Limitations & Phase 3 Roadmap

- **Phase 2 Scope**: Focuses on personal cross-document entity resolution and evidence-backed relationship aggregation across user-selected documents.
- **Phase 3 Possibilities**:
  - Global background knowledge graph compilation across entire collections.
  - Entity-linked multi-hop RAG traversal directly utilizing canonical entity paths during chat retrieval.
  - Interactive manual merge/split overrides in the Knowledge Graph UI for advanced domain curation.

