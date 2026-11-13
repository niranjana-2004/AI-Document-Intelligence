# Cognidocs — Knowledge Intelligence / Personal Knowledge Explorer (Phase 3)

**Status**: **Production Ready (Verified & Frozen)**  
**Feature**: Personal Knowledge Explorer & Cross-Document Intelligence Layer  
**Scope**: Unified, Multi-Source, Source-Grounded Knowledge Intelligence & Concept Exploration  

---

## 1. Executive Summary & Purpose

Cognidocs **Knowledge Intelligence (Phase 3)** establishes a unified intelligence and exploration layer operating across a user's entire document collection. Built on top of the established **Knowledge Graph Phase 1** (single-document grounded graphs) and **Cross-Document Knowledge Graph Phase 2** (canonical entity resolution & cross-document relationship topology), Phase 3 answers high-level user inquiries with structured, source-verifiable knowledge.

Phase 3 answers:
> **"What do my documents know about this concept, how do they relate, and where is the verifiable evidence?"**

### Core Questions Supported
- **Concept Summaries**: *"What do my documents say about TCP?"*
- **Comparative Intelligence**: *"Compare TCP and UDP across my notes and research papers"*
- **Cross-Document Traces**: *"Where is TCP discussed across my collection?"*
- **Contradiction & Conflict Analysis**: *"Which documents disagree or have different perspectives on this topic?"*
- **Source-Grounded Evidence**: *"Show me all the evidence and exact pages for this concept"*

```
                                ┌──────────────────────────────────────┐
                                │   Personal Knowledge Explorer UI     │
                                │   (/knowledge-explorer)              │
                                └──────────────────┬───────────────────┘
                                                   │
                                                   ▼
                                ┌──────────────────────────────────────┐
                                │   Knowledge Intelligence Service     │
                                │   (knowledge_intelligence_service)   │
                                └──────────────────┬───────────────────┘
                                                   │
                    ┌──────────────────────────────┼──────────────────────────────┐
                    ▼                              ▼                              ▼
        ┌───────────────────────┐      ┌───────────────────────┐      ┌───────────────────────┐
        │ Cross-Doc Graph (P2)  │      │ Multi-Source Evidence │      │ Grounded LLM / Ollama │
        │ Canonical Resolution  │      │ Chunks, Notes, Papers │      │ llama3.2 + Fallback   │
        └───────────────────────┘      └───────────────────────┘      └───────────────────────┘
```

---

## 2. Core Architectural Principles & Production Data Path

1. **Lazy, On-Demand Generation Architecture**:
   - Cognidocs does not run expensive upfront graph extraction at document upload time.
   - When a user selects documents and executes an intelligence query, `execute_knowledge_intelligence_query` dynamically invokes `get_or_generate_cross_document_graph`.
   - If a Phase 2 cross-document graph or any underlying Phase 1 single-document graph has not yet been computed for the document's content hash, it is generated just-in-time and persisted atomically into the database.
   - All subsequent queries on the same document set hit the persisted graph snapshots with zero re-computation.
2. **Zero Hallucination / Strict Evidence Grounding**:
   - Every claim in the overview, relationships, and direct answers is linked to concrete document evidence.
   - For unknown or unsupported concepts, the service explicitly returns `grounding_status="insufficient_evidence"` with zero speculative or fabricated statements.
3. **100% Local AI & Deterministic Offline Fallback**:
   - Powered by local Ollama (`llama3.2`) with strictly bounded context windows and low temperature ($0.1$).
   - If Ollama is offline or unavailable, the service deterministically synthesizes the direct answer and insights directly from source evidence without failing.
4. **Multi-Source Evidence Aggregation**:
   - Seamlessly pulls and ranks evidence across:
     - **Standard Printed Documents**: `printed_pdf`, `text_document`, `DocumentChunk`
     - **Handwritten Notes**: `handwritten`, `HandwrittenPage`
     - **Academic Research Papers**: `research_paper`, `ResearchPaperAnalysis` (key claims, methodology, limitations)
   - Every evidence item provides `document_id`, `document_title`, `page_number`, `chunk_id`, and a verbatim source excerpt.
5. **Strict User / Tenant Isolation**:
   - All queries, cached entries, document chunks, handwritten notes, and canonical entities are filtered by authenticated `user_id` at the database query level.
   - Cross-user data leakage is structurally impossible. Unauthorized or mixed document queries are rejected with HTTP 404.
6. **High-Performance SHA-256 Query Caching**:
   - Query results are indexed by `cache_key = SHA-256(user_id : sorted(doc_ids) : normalized_query : version)`.
   - Document order independence is guaranteed (`[12, 14]` and `[14, 12]` hit the identical cache key).
   - Warm queries return in $<100\,\text{ms}$ (measured **$41.5\,\text{ms}$** in certification).

---

## 3. Database Schema

Phase 3 introduces a persistent query cache table in `backend/app/models/knowledge_intelligence_cache.py`:

### Table `knowledge_intelligence_cache`
| Column | Type | Description |
|---|---|---|
| `id` | Integer (PK) | Auto-incrementing primary key |
| `user_id` | Integer (FK) | ForeignKey to `users.id` (CASCADE), indexed |
| `cache_key` | VARCHAR(128) | Deterministic SHA-256 hash, unique index |
| `selected_doc_ids_json` | TEXT | JSON array of sorted document IDs |
| `query_text` | TEXT | Raw input query string |
| `normalized_query` | VARCHAR(255) | Lowercased, stripped, normalized query, indexed |
| `response_json` | TEXT | Full serialized `KnowledgeIntelligenceResponse` JSON |
| `created_at` | DateTime | Timestamp of initial computation |
| `updated_at` | DateTime | Timestamp of last access or refresh |

Idempotent database migration is performed automatically on startup via `ensure_knowledge_intelligence_schema(engine)` in `backend/app/main.py`.

---

## 4. Query Processing Pipeline

```
  User Query: "Compare TCP and UDP"
       │
       ▼
  1. Deterministic Query Parser & Intent Classifier
       ├─ Classifies intent: entity_comparison / concept_summary / conflict_analysis / etc.
       └─ Extracts candidate concept phrases and normalized tokens (stripping stop words)
       │
       ▼
  2. Cross-Document Canonical Entity Resolution
       ├─ Dispatches to Knowledge Graph Phase 2 to ensure graph topology is built/cached
       ├─ Matches candidate terms against canonical entities via exact, acronym, alias, and whole-word matching
       ├─ Disambiguates polysemous terms (e.g., Java programming vs Java island) via domain markers
       └─ Disallows false collision pairs (e.g., TCP != UDP, SYN != SYN Flood)
       │
       ▼
  3. Multi-Source Evidence Retrieval & Ranking
       ├─ Retrieves chunks from standard documents (`DocumentChunk`)
       ├─ Retrieves transcriptions from handwritten notes (`HandwrittenPage`)
       ├─ Retrieves structured claims & evidence from academic papers (`ResearchPaperAnalysis`)
       └─ Ranks and deduplicates evidence items by lexical overlap and relevance score
       │
       ▼
  4. Cross-Document Synthesis & Conflict Detection
       ├─ Detects shared knowledge patterns across multiple documents
       └─ Identifies perspective differences and contradictions (conservative thresholding)
       │
       ▼
  5. Grounded Answer Synthesis
       ├─ Attempts local Ollama (`llama3.2`) synthesis using strictly bounded evidence prompt
       ├─ Validates LLM output against source entities
       └─ Falls back to deterministic rule-based synthesis if Ollama is unreachable
       │
       ▼
  6. Response Assembly & Persistent Caching
       └─ Serializes `KnowledgeIntelligenceResponse` and stores in `knowledge_intelligence_cache`
```

---

## 5. REST API Specifications

### 1. Execute Knowledge Intelligence Query
- **Endpoint**: `POST /documents/knowledge-intelligence/query`
- **Auth**: Bearer JWT (`Authorization: Bearer <token>`)
- **Request Body**:
```json
{
  "query": "What do my documents say about TCP?",
  "document_ids": [12, 14],
  "force_refresh": false
}
```
- **Response**: HTTP 200 `KnowledgeIntelligenceResponse`

### 2. Entity Intelligence Drilldown
- **Endpoint**: `GET /documents/knowledge-intelligence/entity/{entity_key}?document_ids=12,14`
- **Auth**: Bearer JWT
- **Response**: Targeted entity summary with full cross-document citations and relationship edge traversal.

### 3. Clear Knowledge Intelligence Cache
- **Endpoint**: `DELETE /documents/knowledge-intelligence/cache`
- **Auth**: Bearer JWT
- **Response**: `{ "status": "success", "deleted_cache_entries": 4, "message": "Successfully cleared 4 cached knowledge intelligence queries." }`

---

## 6. Frontend Personal Knowledge Explorer Workspace

The frontend interface is implemented in `frontend/src/pages/KnowledgeExplorer.jsx` and styled via `frontend/src/styles/knowledge-explorer.css`:

1. **Document Selection Sidebar**:
   - Live multi-document picker showing document type badges (`PDF`, `Handwritten`, `Research Paper`, `TXT`).
   - Quick "Select All" and "Clear All" controls with real-time selection badge.
2. **Interactive Intelligence Search Bar**:
   - Natural language input with loading indicators and caching status pills.
   - Quick query suggestion chips (*"What do my documents say about TCP?"*, *"Compare TCP and UDP"*, *"Find conflicts or disagreements"*).
3. **Structured 7-Section Response Layout**:
   - **Direct Answer Card**: Grounded synthesis with confidence score, source badges, and citation pills.
   - **Knowledge Overview**: Per-entity synthesized definitions, alias chips, and cross-document presence metrics.
   - **Multi-Source Evidence Drawer**: Grouped by source type (`Standard Document`, `Handwritten Note`, `Research Paper`) with page numbers and verbatim excerpts.
   - **Cross-Document Insights**: Synthesized takeaways spanning multiple documents.
   - **Contradictions & Perspective Differences**: Explicitly flagged differences with source document attribution.
   - **Grounded Relationships**: Directed graph connections ($A \xrightarrow{relates} B$) with confidence indicators.
   - **Related Topics**: Clickable pills to pivot exploration directly to related entities.
4. **Navigation Integration**:
   - Registered under `/knowledge-explorer` in `App.jsx`.
   - Side navigation item in `AppLayout.jsx` with `Compass` icon and `Phase 3` indicator badge.

---

## 7. Verification & Production Certification Metrics

### A. Step 5 Production Query Validation (Queries A through G)
Tested against persisted production documents: Doc 14 (Technical Text), Doc 12 (Handwritten Notes), Doc 5 (107-page Doctoral Thesis), Doc 16 (Related Networking), Doc 3 (DOCX Report):
- **Query A (TCP Collection)**: 514.6ms (warm) / 20.2s (cold Ollama) | Intent: `knowledge_lookup` | Grounded (12 excerpts, 4 insights, 3 relationships)
- **Query B (TCP vs UDP Comparison)**: 465.3ms (warm) / 21.0s (cold Ollama) | Intent: `entity_comparison` | Grounded
- **Query C (Neural Networks across collection)**: 514.8ms (warm) / 8.9s (cold Ollama) | Direct answer clearly states no mentions exist in the selected networking corpus | Zero Hallucination
- **Query D (Handwritten Note Specific)**: 171.0ms (warm) / 10.9s (cold Ollama) | Correctly cites Doc 12 handwritten pages 1 and 2
- **Query E (Research Paper Specific)**: 448.8ms (warm) / 13.9s (cold Ollama) | Correctly cites Doc 5 thesis security sections
- **Query F (Disagreements & Conflicts)**: 460.9ms (warm) | Intent: `conflict_detection` | Conservative conflict classification
- **Query G (Adversarial Unknown Concept "Quantum Teleportation")**: 476.9ms | Grounding Status: `insufficient_evidence` | **Zero Hallucination**

### B. Step 6 Grounding Audit
- Sampled 20 randomized claims across all generated query outputs.
- Verification checks: `document_id`, `document_title`, `page_number`, `chunk_id`, `source_type`, `excerpt`, `confidence`.
- Result: **20 / 20 Verified Grounded (100% Grounded, 0 Invented Citations, 0 Hallucinations)**.

### C. Step 7 Entity Resolution Audit
- Adversarial distinct pairs:
  - `TCP vs UDP`: Separated (`disallowed_pair_guard`)
  - `SYN vs SYN Flood`: Separated (`disallowed_pair_guard`)
  - `Client vs Server`: Separated (`disallowed_pair_guard`)
  - `Encryption vs Decryption`: Separated (`disallowed_pair_guard`)
  - `Precision vs Recall`: Separated (`disallowed_pair_guard`)
  - `Java` (JVM compiler vs Indonesian island): Disambiguated (`context_disambiguation`)
  - `Python` (Scripting language vs Reptile snake): Disambiguated (`context_disambiguation`)
  - `Training vs Testing`: Separated (`insufficient_similarity`)
  - **False Merges: 0**
- Valid merges preserved:
  - `TCP ↔ Transmission Control Protocol` (alias match)
  - `AI ↔ Artificial Intelligence` (alias match)
  - `Python ↔ Python programming language` (lexical equivalence)
  - **Valid Merges Preserved: 3 / 3**

### D. Step 8 Caching & Latency
- Cold Miss Latency: $170.37\,\text{ms}$
- Warm Hit Latency: **$41.48\,\text{ms}$**
- Document Permutation Latency: **$38.89\,\text{ms}$** (cached = True)
- Cache Speedup: **$4.1\times$ to $297\times$**

### E. Step 9 Tenant Isolation
- User B (User 5) requesting User A (User 4) documents: **HTTP 404 Blocked**.
- User B querying mixed documents `[9, 12]`: **HTTP 404 Blocked**.
- User B cache query: **0 rows returned, zero data leakage**.

### F. Step 13 Local Ollama Offline Failure Handling
- Simulated total Ollama outage by pointing to an unreachable port (`http://127.0.0.1:9999`).
- `synthesize_grounded_answer` engaged `deterministic_fallback` seamlessly.
- Returned grounded direct answer and structured insights directly from retrieved document excerpts.

### G. Complete Regression Test Suites
| Test Suite | Files | Tests | Result |
|---|---|---:|:---:|
| Knowledge Intelligence Phase 3 | `test_knowledge_intelligence.py` | 10 | **PASS** |
| Cross-Document Knowledge Graph (P2) | `test_cross_document_knowledge_graph.py` | 9 | **PASS** |
| API Contract & Large Doc Tests | `test_api_contract_and_large_doc.py` | 6 | **PASS** |
| Knowledge Graph Phase 1 | `test_knowledge_graph.py` | 26 | **PASS** |
| Research Paper Analyzer | `test_research_paper_analyzer.py` | 37 | **PASS** |
| Grounded Citations | `test_grounded_citations.py` | 10 | **PASS** |
| Search Service | `test_search_service.py` | 18 | **PASS** |
| Voice Assistant | `test_voice_assistant.py` | 8 | **PASS** |
| Voice Query Recovery | `test_voice_query_recovery.py` | 21 | **PASS** |
| Layout Guided OCR (Phase B) | `test_layout_guided_ocr_phase_b.py` | 22 | **PASS** |
| Email & Auth Verification | `test_email_verification_status.py` | 9 | **PASS** |
| Password Reset Optimization | `test_password_reset_optimization.py` | 4 | **PASS** |
| Manual Edit Protection | `test_manual_edit_protection.py` | 4 | **PASS** |
| OCR 3.5 Recovery | `test_ocr35_recovery.py` | 3 | **PASS** |
| **Total Backend Unit / Regression** | **14 files** | **187** | **187 / 187 PASS** |
| **Frontend Unit Tests** | `frontend/src/utils/*.test.mjs` | **18** | **18 / 18 PASS** |
| **Frontend Production Build** | `vite build` | — | **PASS (1.01s)** |
| **ESLint Quality Check** | `eslint src/...` | — | **0 errors, 0 warnings** |

---

## 8. Database Integrity Verification

| Table | Baseline Before Pass | Final After Certification | Notes |
|---|---:|---:|---|
| `documents` | 102 | 102 | Pristine (untouched) |
| `document_chunks` | 475 | 475 | Pristine (untouched) |
| `handwritten_pages` | 9 | 9 | Pristine (untouched) |
| `research_paper_analyses` | 1 | 1 | Pristine (untouched) |
| `knowledge_graphs` | 1 | 17 | Persisted Phase 1 graphs across test corpus |
| `canonical_entities` | 0 | 282 | Persisted canonical entity resolution clusters |
| `entity_occurrences` | 0 | 785 | Persisted source occurrences and page links |
| `cross_document_knowledge_graphs` | 0 | 7 | Persisted cross-document graphs |
| `cross_document_edges` | 0 | 475 | Persisted grounded inter-document concept connections |
| `knowledge_intelligence_cache` | 0 | 4 | Persisted SHA-256 query cache snapshots |
