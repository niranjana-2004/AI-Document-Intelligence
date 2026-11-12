# Cognidocs — Knowledge Graph Phase 1 Architecture Note

## 1. Objective & Core Principle
Knowledge Graph Phase 1 builds a **source-grounded, typed, explainable entity-relationship graph** for individual Cognidocs documents (printed PDF/DOCX/TXT, handwritten notes/images, academic research papers, and mixed documents). Every displayed node and edge is anchored to concrete document evidence (`chunk_id`, `page`, `section`, verbatim `evidence_excerpt`) with transparent confidence scoring (`High`, `Medium`, `Low`) and explicit provenance (`explicit`, `derived`, `inferred`). No ungrounded LLM hallucinations, no evidence-free edges, and no self-loops are persisted or displayed.

---

## 2. Existing Cognidocs Services Reused (Read-Only / Direct Reuse)
Rather than duplicating ingestion, chunking, embedding, concept extraction, or citation navigation:

1. **Unified Document & Mixed-Page Chunk Assembly**
   - `app.services.research.paper_section_service.assemble_document_chunks(document, db)` & `build_section_hierarchy(units)`
   - Reused read-only to obtain a single ordered stream of `ChunkUnit(chunk_id, chunk_index, page, content, section_title, normalized_role, embedding)` across printed `DocumentChunk` rows, `HandwrittenPage` (`edited_transcription > raw_transcription`), fallback `extracted_text`, and mixed documents, complete with TOC detection (`is_toc_chunk`) and page attribution.
2. **Content Hashing**
   - `app.services.research.paper_analysis_service.compute_research_content_hash(document, units)` (SHA-256 over normalized document chunks/transcriptions) to detect document or edited-transcription changes cleanly.
3. **Concept Normalization & Baseline Extraction**
   - `app.services.document_mind_map_service` (`normalize_concept_label`, `consolidate_concepts`, `extract_standard_concepts_fallback`) and `app.services.handwriting.handwritten_concept_service.list_handwritten_concepts` to reuse existing concept signals without re-implementing base concept mining.
4. **Embeddings, Similarity & Retrieval**
   - `app.services.embedding_services.generate_embedding` (`all-MiniLM-L6-v2`) and `app.services.similarity_service.cosine_similarity` for semantic node deduplication and candidate pair similarity scoring.
   - `app.services.search_service.semantic_search` / keyword scoring helpers when locating supporting chunks for candidate entities.
5. **Cached Research Paper Analysis Enrichment**
   - Query `ResearchPaperAnalysis` by `(document_id, user_id)` when `content_hash` matches: promotes verified paper elements (`Problem`, `Method`, `Model`, `Dataset`, `Baseline`, `Metric`, `Result`, `Limitation`, `Future Work`) with their already-verified evidence pointers directly into typed Knowledge Graph nodes and structural chain candidates.
6. **Local LLM Client**
   - `app.services.handwriting.ollama_client.query_ollama_json` (`llama3.2`, bounded `num_ctx=4096`, `num_predict=550`, `timeout=35`) for bounded candidate relationship verification, with full deterministic fallback when Ollama is offline or `skip_llm=True`.
7. **Frontend Pan/Zoom & Citation Routing**
   - `frontend/src/utils/mindMapLayout.js` (`clampView`, `computeFitTransform`, `computeResetTransform`)
   - `frontend/src/utils/citationUtils.js` (`buildSourceNavigationUrl`, `extractSearchableSnippet`) so `Source Page` jumps accurately to `/handwritten/:id?page=...` or `/documents?doc=...&page=...`.

---

## 3. New Backend Modules (`backend/app/`)
Clean single-responsibility separation:

1. `models/knowledge_graph.py`
   - `KnowledgeGraph`, `KnowledgeGraphNode`, `KnowledgeGraphEdge`, plus `ensure_knowledge_graph_schema(engine=None)`.
2. `schemas/knowledge_graph.py`
   - Controlled node types (`Concept`, `Entity`, `Method`, `System`, `Dataset`, `Metric`, `Person`, `Organization`, `Attack`, `Protocol`, `Defense`, `Problem`, `Result`, `Limitation`, `FutureWork`, `Document`, `Section`).
   - Controlled 20-relationship vocabulary (`ALLOWED_RELATIONSHIPS` + `RELATIONSHIP_ALIASES` mapping free-form verbs like `exploits` / `mitigates` / `introduces` to canonical predicates).
   - Structured `EvidenceRef`, `ConfidenceBreakdown`, `KnowledgeGraphNodeOut`, `KnowledgeGraphEdgeOut`, `KnowledgeGraphResponse`, `KnowledgeGraphGenerateRequest`.
3. `services/knowledge_graph_repository.py`
   - Persistence, `(user_id, document_id)` ownership-scoped lookup, hash/version staleness detection, and deletion.
4. `services/knowledge_graph_evidence_service.py`
   - Filters TOC/empty chunks, extracts clean verbatim excerpts aligned to subject/object entities, attaches `chunk_id`, `page`, `section`, computes evidence strength, and strips any evidence-free or out-of-range claim.
5. `services/knowledge_graph_extraction_service.py`
   - Merges Research Paper Analysis entities (if cached & valid), technical/acronym/definition terms, heading concepts, and reused Mind Map/Handwritten concepts.
   - Filters generic filler (`information`, `system`, `process`, `data`, `thing`, `area`, `study`, etc.) unless central; deduplicates case/hyphen/plural/acronym variants via hybrid lexical + cosine similarity + context window matching and stores merged surface forms in `aliases`.
6. `services/knowledge_graph_relationship_service.py`
   - **Stage A (Deterministic Candidate Discovery)**: Intra-sentence pattern matching (`is a`, `uses`, `depends on`, `causes`, `leads to`, `results in`, `mitigates`, `protects against`, `part of`, `defined as`, `measured by`, `evaluated on`, `compared with`, `improves`, `degrades`, `supports`, `contradicts`, `precedes`, `follows`), section/co-occurrence proximity, and Research Paper structural chains — keeping candidate volume linear/bounded rather than quadratic `O(N^2)`.
   - **Stage B (Bounded LLM Verification + Fallback)**: Sends small evidence-backed candidate batches (`<= 15` pairs per batch, max 2 batches) to `query_ollama_json` (`skip_llm` or timeout falls back cleanly to deterministic candidates). Normalizes predicates onto the 20-verb vocabulary, rejects self-loops (`A == B`), deduplicates `(source_key, relationship, target_key)`, and computes transparent multi-signal confidence (`evidence_count_score`, `proximity_score`, `explicitness_score`, `semantic_score`, `llm_agreement_score`).
7. `services/knowledge_graph_service.py`
   - Orchestrates ownership check (`404` for missing or non-owned doc), hash/version cache hit vs rebuild, `regenerate`, `delete`, default low-confidence edge filtering (`include_low_confidence=False` hides `< 0.50` edges from UI by default), and internal diagnostics.
8. `api/routes/knowledge_graph.py`
   - FastAPI router mounted at `/documents`:
     - `POST /documents/{document_id}/knowledge-graph`
     - `GET /documents/{document_id}/knowledge-graph`
     - `DELETE /documents/{document_id}/knowledge-graph`
     - `POST /documents/{document_id}/knowledge-graph/regenerate`

---

## 4. Database Schema & Phase 2 Multi-Document Readiness
- **`knowledge_graphs`**: `id`, `user_id` (FK `users.id`), `document_id` (FK `documents.id`), `content_hash`, `graph_version` (`"kg-v1"`), `status` (`"ready"` | `"empty"` | `"failed"`), `generation_method`, `stats_json`, `diagnostics_json`, `created_at`, `updated_at`.
- **`knowledge_graph_nodes`**: `id`, `graph_id` (FK `knowledge_graphs.id` cascade), `document_id` (FK `documents.id`), `user_id` (FK `users.id`), `node_key`, `label`, `normalized_label`, `node_type`, `description`, `aliases_json`, `confidence`, `confidence_tier`, `importance_score`, `evidence_count`, `source_pages_json`, `evidence_json`, `metadata_json`.
- **`knowledge_graph_edges`**: `id`, `graph_id` (FK `knowledge_graphs.id` cascade), `document_id` (FK `documents.id`), `user_id` (FK `users.id`), `source_node_id` (FK `knowledge_graph_nodes.id`), `target_node_id` (FK `knowledge_graph_nodes.id`), `source_key`, `target_key`, `relationship`, `origin` (`explicit` | `derived` | `inferred`), `confidence`, `confidence_tier`, `confidence_breakdown_json`, `evidence_count`, `source_pages_json`, `evidence_json`.
- **Phase 2 compatibility**: Storing explicit `document_id`, `user_id`, `node_key`, `normalized_label`, `aliases_json`, and relational node/edge rows allows Phase 2 multi-document graphs to align nodes across `document_id IN (...)` without altering Phase 1 tables.

---

## 5. Caching & Invalidation Strategy
- `content_hash` is computed from all active document chunks / edited handwritten transcriptions (and includes cached `ResearchPaperAnalysis.content_hash` + `updated_at` marker when present).
- `GET` returns the cached graph immediately if `(user_id, document_id)` exists, marking `is_outdated=True` only if underlying `content_hash` or `GRAPH_VERSION` changed.
- `POST` returns cache hit if `(content_hash, GRAPH_VERSION)` matches and `force_refresh=False`; otherwise rebuilds atomically and replaces prior graph nodes/edges for that `(user_id, document_id)`.

---

## 6. Frontend Integration (`frontend/src/`)
- Dedicated workspace `/knowledge-graph` (`KnowledgeGraph.jsx` + `frontend/src/styles/knowledge-graph.css`) linked in `AppLayout.jsx` sidebar and cross-linked with `MindMap.jsx`.
- Dual-mode UI:
  1. **Interactive Canvas**: Clustered (grouped by node type), Hierarchical (layered topological levels), and Force-seeded layouts with SVG directed labeled edges, node search + auto-focus, type/relationship/confidence filters, neighborhood isolation (`1-hop` focus / hide unrelated), `A -> B` shortest-path tracer, zoom/pan/fit/reset controls, and `Source Page` + verbatim `Evidence` drawer.
  2. **Accessible List / Table View**: Keyboard-navigable structured node & relationship explorer so users can inspect every node, edge, confidence score, provenance tag, and source page without depending solely on canvas pointer interactions.

