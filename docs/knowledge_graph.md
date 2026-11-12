# Cognidocs — Knowledge Graph (Phase 1)

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

## Known Limitations & Phase 2 Roadmap
- **Scope**: Phase 1 builds single-document graphs (`document_id`-scoped). Multi-document cross-linking, global entity resolution across collections, and entity-linked RAG traversal belong to **Knowledge Graph Phase 2** (which the relational schema already anticipates via `document_id`, `user_id`, `node_key`, `normalized_label`, and `aliases_json`).
- **Complex Multi-Hop & Coreference**: Deterministic pattern extraction handles intra-sentence and adjacent-sentence links well; complex cross-paragraph pronoun coreference depends on local LLM verification (`skip_llm=false`) and conservative thresholding to avoid hallucinating speculative edges.
- **Noisy OCR Handwritten Pages**: Severely corrupted handwritten OCR words without manual correction may yield fewer explicit directional edges than clean printed PDFs; editing the handwritten transcription automatically marks cached graphs `is_outdated=True` for one-click regeneration.

