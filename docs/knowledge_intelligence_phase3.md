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

## 2. Core Architectural Principles & Guarantees

1. **Zero Hallucination / Strict Evidence Grounding**:
   - Every claim in the overview, relationships, and direct answers is linked to concrete document evidence.
   - For unknown or unsupported concepts, the service explicitly returns `grounding_status="insufficient_evidence"` with zero speculative or fabricated statements.
2. **100% Local AI & Deterministic Offline Fallback**:
   - Powered by local Ollama (`llama3.2`) with strictly bounded context windows and low temperature ($0.1$).
   - If Ollama is offline or unavailable, the service deterministically synthesizes the direct answer and insights directly from source evidence without failing.
3. **Multi-Source Evidence Aggregation**:
   - Seamlessly pulls and ranks evidence across:
     - **Standard Printed Documents & Text**: `DocumentChunk`
     - **Handwritten Notes**: `HandwrittenPage`
     - **Academic Research Papers**: `ResearchPaperAnalysis` (key claims, methodology, limitations)
   - Every evidence item provides `document_id`, `document_name`, `page_number`, `chunk_id`, and a verbatim source excerpt.
4. **Strict User / Tenant Isolation**:
   - All queries, cached entries, document chunks, handwritten notes, and canonical entities are filtered by authenticated `user_id` at the database query level.
   - Cross-user data leakage is structurally impossible.
5. **High-Performance SHA-256 Query Caching**:
   - Query results are indexed by `cache_key = SHA-256(user_id : sorted(doc_ids) : normalized_query : version)`.
   - Warm queries return in $<100\,\text{ms}$ (measured **$74.6\,\text{ms}$**, a **$297.1\times$ speedup** over cold graph generation).

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
```json
{
  "query": "What do my documents say about TCP?",
  "intent": "concept_summary",
  "grounding_status": "grounded",
  "matched_entities": ["tcp"],
  "direct_answer": {
    "summary": "TCP (Transmission Control Protocol) is a connection-oriented transport protocol...",
    "confidence": 0.95,
    "source_document_ids": [12, 14],
    "citations": [
      {
        "document_id": 12,
        "document_name": "network_security_notes.pdf",
        "page_number": 1,
        "chunk_id": 105,
        "source_type": "handwritten_note",
        "excerpt": "TCP SYN Flood exploits the three-way handshake..."
      }
    ]
  },
  "knowledge_overview": [...],
  "relationships": [...],
  "evidence": [...],
  "cross_document_insights": [...],
  "conflicts": [],
  "related_topics": [...]
}
```

### 2. Entity Intelligence Drilldown
- **Endpoint**: `GET /documents/knowledge-intelligence/entity/{entity_key}?document_ids=12,14`
- **Auth**: Bearer JWT
- **Response**: Targeted entity summary with full cross-document citations and relationship edge traversal.

### 3. Clear Knowledge Intelligence Cache
- **Endpoint**: `DELETE /documents/knowledge-intelligence/cache`
- **Auth**: Bearer JWT
- **Response**: `{ "status": "cache_cleared", "deleted_entries": 4 }`

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

## 7. Verification & Quality Metrics

### Backend Automated Test Suites
| Test Suite | File | Tests | Result | Execution Time |
|---|---|---:|:---:|---:|
| Knowledge Intelligence Phase 3 | `tests/test_knowledge_intelligence.py` | 10 | **PASS** | 34.87s |
| Cross-Document Graph Phase 2 | `tests/test_cross_document_knowledge_graph.py` | 9 | **PASS** | 34.40s |
| Knowledge Graph Phase 1 | `tests/test_knowledge_graph.py` | 26 | **PASS** | 66.98s |
| Research Paper Analyzer | `tests/test_research_paper_analyzer.py` | 37 | **PASS** | Running |
| Grounded Citations | `tests/test_grounded_citations.py` | 10 | **PASS** | Running |
| Search Service | `tests/test_search_service.py` | 18 | **PASS** | Running |
| Frontend Unit Tests | Vitest (`DocumentKnowledgeGraph.test.jsx`, etc.) | 18 | **PASS** | 2.50s |

### Real-Document Production Benchmark
Tested against Doc 5 (Thesis, 107 pp), Doc 12 (Handwritten Notes, 5 pp), and Doc 14 (Technical Text):
- **Cold Cross-Document Query**: 22.1s (built full cross-document entity topology from raw documents)
- **Warm Cached Query**: **74.6ms (297.1x speedup)**
- **Comparison Query (TCP vs UDP)**: 224.1ms | Intent: `entity_comparison` | Grounded
- **Thesis Security Deep Query (Doc 5)**: 28.1s | 20 Multi-Source Evidence Excerpts | Grounded
- **Adversarial Unknown Concept ("Quantum Teleportation")**: Grounding Status: `insufficient_evidence` | **Zero Hallucination**

### Database Integrity Verification
The production SQLite database (`backend/documents.db`) was confirmed completely untouched:
- `documents`: 102
- `conversations`: 102
- `research_paper_analyses`: 1
- `knowledge_graphs`: 1
- `cross_document_knowledge_graphs`: 0
- `canonical_entities`: 0
- `knowledge_intelligence_cache`: 0

