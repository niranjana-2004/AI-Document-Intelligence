# Cognidocs Multi-Document Chat — Phase 1: Smallest Safe Extension Design

**Date**: November 2026  
**System**: Cognidocs AI Document Intelligence  
**Component**: Cross-Document Source-Grounded AI Conversation  
**Status**: Step 2 Architecture Design  

---

## 1. Executive Summary & Design Philosophy

Cognidocs already possesses a functional, tested single-document and collection-level chat pipeline built around:
- `POST /documents/ask`
- `QuestionRequest` (with `document_id`, `document_ids`, `conversation_history`, `conversation_id`)
- `resolve_follow_up_query()`
- `build_context()`
- `semantic_search()` using `all-MiniLM-L6-v2`
- `generate_response()` using local Ollama `llama3.2:latest`
- Persistent conversation storage in `conversations` and `conversation_messages`

The objective of this milestone is **not** to create a parallel or disconnected multi-document chat engine. Rather, it is to extend the existing single-document pipeline into a **document-aware, diversity-balanced, source-grounded cross-document conversational engine** that seamlessly handles:
1. Pure printed documents (PDF, DOCX, TXT)
2. Pure handwritten documents (OCR 3.5 transcriptions)
3. Mixed printed and handwritten document sets

---

## 2. Comparison of Existing vs. Extended Execution Paths

### 2.1 Existing Path
```
POST /documents/ask
      ↓
QuestionRequest (single document_id or unconstrained collection)
      ↓
resolve_follow_up_query()
      ↓
build_context()
      ↓
semantic_search() (Global top_k sort; risk of one document monopolizing results)
      ↓
Generic single-document LLM prompt in llm_service.py
      ↓
Inline numeric citations [1], [2]
      ↓
ConversationMessage persisted with basic chunk metadata
```

### 2.2 New Multi-Document Path
```
POST /documents/ask
      ↓
QuestionRequest (effective_document_ids: list[int])
      ↓
Strict JWT Ownership Guard (Verifies all IDs belong to current_user; rejects unauthorized with HTTP 404)
      ↓
Handwritten Chunk Synchronization Check (Ensures handwritten documents have indexed DocumentChunk records)
      ↓
resolve_follow_up_query() (Conversational resolution: "it", "the second one", topic tracking)
      ↓
multi_document_semantic_search() (Hybrid semantic + BM25 keyword + Section boost)
      ↓
Document-Aware Diversity Balancing & Deduplication (Caps single-doc dominance; guarantees representation for relevant docs)
      ↓
Normalized Evidence Objects (document_id, document_title, source_type, page, chunk_id, excerpt, similarity)
      ↓
Document-Aware Context Framing (Explicit document boundaries, types, and citations)
      ↓
Cross-Document Synthesis LLM Prompt (Compare, synthesize, distinguish common vs. unique vs. conflicting claims)
      ↓
Ollama Llama 3.2 (with resilient fallback if unavailable or low confidence < 0.40)
      ↓
Deterministic Grounded Follow-up Question Generator (2–3 grounded questions if evidence is strong)
      ↓
ConversationScope Persistence (Conversation.selected_doc_ids preserved across dialogue turns)
```

---

## 3. Backward Compatibility Guarantees

1. **Single-Document Requests**:
   - Requests providing `{"query": "...", "document_id": 12}` continue to pass into the search pipeline with `effective_document_ids = [12]`.
   - Single-document context formatting and response structures remain 100% compatible.
2. **Collection-Wide Requests**:
   - Requests with `document_id = None` and `document_ids = None` query the user's entire library as before.
3. **Multi-Document Requests**:
   - Requests providing `{"query": "...", "document_ids": [3, 7, 13]}` now activate document-aware diversity balancing, cross-document context framing, and comparison synthesis.
4. **Existing Frontend Contract**:
   - `results` array in the JSON response preserves all existing keys (`chunk_id`, `document_id`, `filename`, `page_number`, `chunk_index`, `content`, `similarity`, `citation_index`) while enriching them with `document_title`, `source_type` ("printed" | "handwritten"), and `excerpt`.

---

## 4. Key Subsystem Specifications

### 4.1 Strict Multi-Tenant Ownership Guard
- Before any retrieval or indexing, the backend queries `db.query(Document.id).filter(Document.user_id == current_user.id, Document.id.in_(effective_document_ids))`.
- If `owned_count != len(effective_document_ids)`, the request is terminated with `HTTP 404 Not Found`.
- Zero metadata or existence information is disclosed about unauthorized documents.

### 4.2 Handwritten Document Synchronization Bridge
- Before search execution, the engine checks if any selected document has `is_handwritten == True`.
- If so, it verifies that `DocumentChunk` records exist. If missing or empty, it invokes `sync_handwritten_chunks_and_embeddings(doc_id, db)` from `handwritten_source_service.py`.
- This ensures that handwritten notes transcribed via OCR 3.5 participate directly in semantic vector search and page-level citations.

### 4.3 Document-Aware Diversity Balancing Algorithm
When multiple documents are selected:
1. Chunks from all selected documents are scored using hybrid semantic similarity ($0.70$) + keyword overlap ($0.30$) + intent/section boost.
2. Candidate chunks are filtered by minimum relevance threshold ($0.25$) and relative drop-off ($0.60 \times \text{top\_score}$).
3. To prevent a large document from crowding out other relevant documents:
   - Calculate maximum allowed chunks per document: $\text{cap} = \max(2, \lceil \text{top\_k} / |\text{selected\_docs}| \rceil + 1)$.
   - Chunks are selected in round-robin or stratified score order, guaranteeing that every document with high-quality evidence is represented.
   - Near-duplicate chunks ($>0.88$ token cosine similarity or duplicate content) are pruned.
4. Total evidence is bounded to `top_k` (typically 6–10 chunks).

### 4.4 Document-Aware Context Formatting
Context provided to Llama 3.2 clearly separates documents:
```text
[Source 1 | Document: "Project Report - LLM" | Type: Printed | Page: 3 | Chunk: 12]
<chunk text>

[Source 2 | Document: "Python Handwritten Notes" | Type: Handwritten | Page: 1 | Chunk: 4]
<OCR transcription text>
```

### 4.5 Cross-Document Synthesis Prompt
The system instructions enforce:
- Factual grounding exclusively in the provided sources.
- Inline bracketed citations matching the source headers (`[1]`, `[2]`).
- Clear synthesis when comparing documents (noting common points, unique points, and any conflicting statements).
- Immediate fallback to `FALLBACK_ANSWER` if the evidence is insufficient.

### 4.6 Multi-Document Cache & Version Invalidation
- Cache key: `hashlib.sha256(f"{user_id}:{sorted(document_ids)}:{content_hashes}:{normalized_query}".encode())`.
- If any selected document is re-uploaded, edited, or re-transcribed, its `content_hash` changes, instantly invalidating stale responses.

