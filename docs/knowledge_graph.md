# Cognidocs — Knowledge Graph (Phase 1)

**Status**: **FROZEN (Production Ready)**  
**Feature**: Source-Grounded Document Knowledge Graph  
**Target**: Single-Document Grounded Knowledge Graph with Deterministic & Hybrid (Ollama `llama3.2`) Verification

---

## Overview
The Cognidocs **Source-Grounded Knowledge Graph** extracts verifiable entities/concepts and typed, directional relationships from an individual document—whether printed (`PDF`, `DOCX`, `TXT`), handwritten (`HandwrittenPage` OCR / edited transcription), academic research paper, or mixed slide/note document. Every displayed node and edge links directly back to concrete source chunks, page numbers, and verbatim excerpts.

---

## Core Design Principles
1. **Strictly Source-Grounded**: Zero invented concepts or evidence-free edges. Every node and edge carries `EvidenceRef` pointers (`chunk_id`, `page`, `section`, verbatim `excerpt`) extracted from active substantive document chunks (excluding Table of Contents / index boilerplate).
2. **Controlled Relationship Vocabulary (20 Predicates)**:
   `contains`, `related_to`, `depends_on`, `causes`, `results_in`, `uses`, `implements`, `extends`, `part_of`, `example_of`, `defined_by`, `measured_by`, `evaluated_on`, `compared_with`, `improves`, `degrades`, `supports`, `contradicts`, `precedes`, `follows`.
   Domain verbs (e.g., `exploits` -> `depends_on`, `mitigates` -> `contradicts`, `leads to` -> `results_in`) are normalized deterministically; unmappable verbs are rejected.
3. **Provenance & Transparent Confidence Scoring**:
   - Edge `origin`: `explicit` (directly stated in text), `derived` (proximity/structural co-occurrence), or `inferred`.
   - Multi-signal `confidence_breakdown`: `evidence_count_score`, `proximity_score`, `explicitness_score`, `semantic_score`, and `llm_agreement_score`.
   - Confidence tiers: **High** (`>= 0.75`), **Medium** (`0.50–0.74`), **Low** (`< 0.50`, stored in SQLite but hidden by default unless **Show Low-Confidence Edges** is enabled).
4. **Reuse-First Integration**:
   - Reuses unified chunk assembly & TOC filtering (`assemble_document_chunks`, `build_section_hierarchy`), SHA-256 content hashing, MiniLM embeddings (`all-MiniLM-L6-v2`) for semantic deduplication, `HandwrittenConcept` / Mind Map concept signals, cached `ResearchPaperAnalysis` entities when available, local Ollama (`llama3.2`) with bounded context/timeouts + full deterministic fallback, and `buildSourceNavigationUrl` for direct Source Page jumping.

---

## API Reference
All endpoints require JWT authentication (`Authorization: Bearer <token>`) and verify strict document ownership (`404` otherwise):

| Endpoint | Method | Purpose |
|---|---|---|
| `/documents/{document_id}/knowledge-graph` | `POST` | Return valid cache if hash/version match (unless `force_refresh=true`), or extract, verify, persist, and return Knowledge Graph JSON. Supports `skip_llm`, `include_low_confidence`, `max_nodes`. |
| `/documents/{document_id}/knowledge-graph` | `GET` | Fetch cached Knowledge Graph (`404` if none built yet) and report `is_outdated` if document chunks, handwritten transcriptions, or research analysis changed. Supports `?include_low_confidence=true`. |
| `/documents/{document_id}/knowledge-graph/regenerate` | `POST` | Force full rebuild and atomically replace previous graph snapshot. |
| `/documents/{document_id}/knowledge-graph` | `DELETE` | Delete persisted Knowledge Graph snapshot, nodes, and edges. |

---

## Frontend Workspace (`/knowledge-graph`)
- **Layouts**: **Clustered** (grouped by node type), **Hierarchical** (directed dependency layers), and **Force** (seeded deterministic spring-repulsion).
- **Exploration Tools**: Node/alias search, node type chips, relationship dropdown, confidence tier filter (`high`/`medium`/`low`), **Isolate 1-Hop Neighborhood**, shortest **Path Finder (`A -> B`)**, Zoom/Pan/Fit/Reset canvas controls, and **Table View** for accessible keyboard/screen-reader browsing.
- **Evidence Drawer**: Inspect any node or edge to view confidence factor bars, merged aliases, connected relationships, verbatim evidence excerpts, and **Open Source Page** deep-linking to `/documents?doc=...&page=...` or `/handwritten/:id?page=...`.

---

## Hardening & Production Optimization

Phase 1 underwent comprehensive performance profiling, index-backed optimization, live local LLM (`llama3.2`) verification, edge evidence auditing, and regression testing.

### 1. Large-Document Sentence Inverted Index Optimization
- **Problem**: Baseline relation and evidence lookup scaled quadratically against large document sentence spans ($O(N_{pairs} \times N_{spans})$). On Document `#5` (160-page thesis, 363 chunks, 5,379 sentence spans), linear regex scanning over 377 candidate pairs required **412.67 seconds**.
- **Solution**:
  - Implemented `build_sentence_inverted_index(spans)` in `knowledge_graph_evidence_service.py` to index words to span indices in memory.
  - In `knowledge_graph_relationship_service.py`, pre-computed sentence occurrence indices (`src_span_indices`, `tgt_span_indices`) are passed directly to `find_pair_evidence`, reducing pair-evidence resolution to $O(1)$ set intersections.
- **Results**:
  - Doc `#5` latency dropped from **412.67s** to **16.58s** (**24.9x overall speedup**).
  - Relationship and evidence lookup stage dropped from **390.3s** to **2.94s** (**>132x stage speedup**).
  - Preserved 100% strict grounding fidelity with zero reliance on external graph databases.

| Document | Type | Pages | Chunks / Spans | Baseline Time | Optimized Time | Speedup Factor |
|---|---|---:|---:|---:|---:|---:|
| **Doc #12** | Handwritten Notes PDF | 7 | 8 chunks / 72 spans | 13.37s | **9.31s** | **1.4x** |
| **Doc #13** | Handwritten Python Image | 1 | 1 chunk / 6 spans | 0.47s | **0.51s** | ~1.0x |
| **Doc #2** | Academic Research Paper PDF | 8 | 42 chunks / 555 spans | 4.46s | **2.74s** | **1.6x** |
| **Doc #5** | 160-Page Thesis PDF | 160 | 363 chunks / 5,379 spans | **412.67s** | **16.58s** | **24.9x** |

### 2. Candidate Pair Lifecycle & Diagnostic Tracking
The relationship service explicitly tracks all candidate pair transitions in the diagnostics payload:
- `raw_candidate_pairs`: Syntactic cues, co-occurrence, and structural patterns discovered.
- `filtered_candidate_pairs`: Candidates surviving self-loop and predicate validity checks.
- `verified_pairs`: Candidate pairs backed by concrete sentence/chunk document evidence.
- `accepted_edges`: Final top-ranked, deduplicated, and visually budgeted edges.
- `rejected_evidence_free_pairs`: Speculative pairs rejected due to lack of document evidence.
- `llm_batches`, `llm_verified_count`, `llm_rejected_ungrounded`, `llm_rejected_invalid_rel`, `llm_fallback_used`, `llm_total_latency_ms`.

### 3. Live Local Ollama (`llama3.2`) Stage B Validation
- Validated with local Ollama (`llama3.2:latest`, 3.2B Q4_K_M) on GPU (NVIDIA RTX 2050):
  - Refined 15 relationships on Doc #12 in 18,069 ms.
  - Refined 12 relationships on Doc #2 in 25,017 ms.
- **Safety Gates**:
  - LLM-suggested entities not found in extracted nodes are 100% rejected (`llm_rejected_ungrounded`).
  - LLM-suggested verbs not matching the 20 controlled predicates or synonym mappings are 100% rejected (`llm_rejected_invalid_rel`).
  - Network timeouts (bounded at 35s) or malformed responses gracefully trigger fallback (`llm_fallback_used`), returning the Stage A deterministic graph without user-facing errors.

### 4. Strict Evidence & Node Quality Audit
- **Evidence Audit**: 100% of tested edges contain valid `EvidenceRef` objects, valid document page numbers, and context-aligned predicates.
- **OCR Noise Filtering**: Pronouns, sentence-initial conjunctions, and OCR header artifacts are cleanly filtered (0.0% generic filler ratio).
- **Domain Coverage**: 100% of domain concepts on technical documents (e.g., `TCP`, `SYN Flood`, `TCB`, `SYN`, `ACK`, `Half-Open Attack`, `Stateful Firewall`) are extracted and preserved.

### 5. Regression & Verification Matrix
- `tests.test_knowledge_graph`: **26/26 OK** (47.35s)
- Research Paper + Citations + Search regression: **65/65 OK** (64.02s)
- Voice + Voice Recovery + Layout OCR regression: **51/51 OK** (71.91s)
- Email Verification regression: **9/9 OK** (10.39s)
- Frontend unit tests (`node --test src/utils/*.test.mjs`): **17/17 passed**
- ESLint: **0 errors, 0 warnings**
- Vite production build: **PASS** (1.23s)
- Database integrity: `documents=102`, `conversations=102`, `research_paper_analyses=1` strictly preserved.

---

## Known Limitations & Phase 2 Roadmap
- **Scope**: Phase 1 builds single-document graphs (`document_id`-scoped). Multi-document cross-linking, global entity resolution across collections, and entity-linked RAG traversal belong to **Knowledge Graph Phase 2** (which the relational schema already anticipates via `document_id`, `user_id`, `node_key`, `normalized_label`, and `aliases_json`).
- **Complex Multi-Hop & Coreference**: Deterministic pattern extraction handles intra-sentence and adjacent-sentence links well; complex cross-paragraph pronoun coreference depends on local LLM verification (`skip_llm=false`) and conservative thresholding to avoid hallucinating speculative edges.
- **Noisy OCR Handwritten Pages**: Severely corrupted handwritten OCR words without manual correction may yield fewer explicit directional edges than clean printed PDFs; editing the handwritten transcription automatically marks cached graphs `is_outdated=True` for one-click regeneration.

