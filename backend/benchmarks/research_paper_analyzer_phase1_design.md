# Cognidocs — Research Paper Analyzer (Phase 1) Architecture Design

## Overview

Phase 1 delivers **Source-Grounded Structured Research Paper Analysis**: identifying whether an uploaded Cognidocs document is an academic/research paper from its content, building a source-linked section hierarchy, extracting structured facts/metrics/tables/figures anchored to verified document chunks & pages, separating **Explicit**, **Derived**, and **Inferred** claims, and providing an interactive UI with an Evidence Drawer linked to the document viewer.

Phase 1 explicitly excludes critical peer review, research-gap generation, literature synthesis across multiple papers, web citation search, and knowledge graphs (reserved for future phases).

---

## 1. Existing Architecture Reused

- **Document Storage & Chunks**: `app.models.document.Document` and `app.models.document_chunk.DocumentChunk` (`page_number`, `chunk_index`, `content`, `embedding`, `category`) plus `app.models.handwritten_page.HandwrittenPage` (`edited_transcription` priority over `raw_transcription`).
- **Source Assembly & Hashing**: `app.services.handwriting.handwritten_source_service.get_document_transcription_source` and SHA-256 `content_hash` versioning pattern from `app.models.document_mind_map.DocumentMindMap` / `app.services.document_mind_map_service.compute_text_hash`.
- **Retrieval & Embeddings**: `app.services.embedding_services.generate_embedding` (`all-MiniLM-L6-v2` cached singleton) and `app.services.similarity_service.cosine_similarity` for mapping/re-verifying extracted claims against `DocumentChunk` records.
- **Local LLM**: Existing `app.services.handwriting.ollama_client.query_ollama_json` / `extract_json_from_text` (`settings.OLLAMA_MODEL`, local Ollama HTTP endpoint), reusing the same local inference pattern without creating a second LLM client.
- **Authentication & Tenant Isolation**: `app.api.dependencies.get_current_user` (JWT) + strict `(Document.id == document_id, Document.user_id == current_user.id)` ownership checks.
- **Frontend Navigation & Deep-Linking**: `AppLayout` sidebar, React Router protected routes (`App.jsx`), `apiRequest` (`frontend/src/services/api.js`), theme CSS custom properties (`frontend/src/index.css`), and `buildSourceNavigationUrl` (`frontend/src/utils/citationUtils.js`) to open `/documents?doc=...&page=...&highlight=...` or `/handwritten/:id?page=...&highlight=...`.

---

## 2. New Services (`backend/app/services/research/`)

1. **`paper_detector.py`**:
   - Content-based academic/research paper detector (never relies on filename alone).
   - Evaluates multi-signal weighted evidence over ordered document chunks and reconstructed page text:
     - Standard academic structural headings (`abstract`, `keywords`/`index terms`, `introduction`, `related work`/`literature review`, `methodology`/`methods`/`proposed system`/`architecture`, `experiments`/`experimental setup`, `results`/`evaluation`/`performance analysis`, `discussion`, `conclusion`, `references`/`bibliography`).
     - Front-matter metadata cues (DOI / ISSN / arXiv / IEEE / Springer / ACM / journal volume / thesis submission notices, author-affiliation email blocks).
     - Citation density (`[1]`, `[12, 14]`, `(Author et al., 2023)`, `et al.`) and numbered bibliography entries.
     - Visual artifact references (`Table N`, `Figure N` / `Fig. N`, `Algorithm N`, `Equation (N)`).
     - Counter-signals for resumes/CVs (`career aspiration`, `educational qualifications`, `internships done`, `curriculum vitae`), invoices, and ultra-short/handwritten personal notes so false positives are suppressed.
   - Produces: `is_research_paper`, `confidence` (`0.0–1.0`), `document_classification` (`research_paper` | `borderline_technical` | `non_research`), `signals`, `missing_signals`, and `detection_notes`. Supports manual override (`classification_override`: `"research_paper" | "non_research" | "auto"`).

2. **`paper_section_service.py`**:
   - Reconstructs ordered `(page_number, chunk_id, chunk_index, text)` units across printed PDFs, DOCX/TXT, and handwritten documents.
   - Detects real structural headings while filtering out dotted Table of Contents entries (`"5.1 Setup ..... 66"`), running page headers/footers (`ISSN`, `Page | N`), and figure/table captions.
   - Preserves original section heading titles while assigning normalized roles (`abstract`, `introduction`, `related_work`, `methodology`, `experiments`, `results`, `discussion`, `conclusion`, `references`, `appendix`, `other`), hierarchy levels (`1`, `2`, `3`), `page_start` / `page_end`, `chunk_ids`, and concise preview snippets.

3. **`paper_evidence_service.py`**:
   - Grounds extracted claims, numerical metrics, and table/figure references directly to `DocumentChunk` records:
     - Locates best matching chunk using keyword/numeric overlap + substring / `cosine_similarity` when needed.
     - Extracts a verbatim short excerpt (`<= 240` chars), records `document_id`, `chunk_id`, `page`, `section`, optional `figure_or_table`, `fact_type` (`explicit` | `derived` | `inferred`), and `confidence`.
     - Computes `evidence_coverage` (ratio of claims backed by verifiable source excerpts).
     - Rejects/downgrades unverified numeric/fact assertions instead of inventing unsupported citations.

4. **`paper_extraction_service.py`**:
   - Bounded, CPU-friendly deterministic + local Ollama extraction pipeline:
     - **Deterministic extraction (always runs first, zero LLM cost)**:
       - Front-matter extraction (title candidate, authors, affiliations, abstract, keywords, DOI/ISSN/venue/year).
       - Numerical metric & setup extractor (`accuracy`, `precision`, `recall`, `f1`, `auc`, `loss`, `runtime`/`latency`, `dataset_size`, `sample_count`, `train/test split`, `parameter_count`, experimental units/comparisons) preserving exact raw value, unit, context, and chunk/page link.
       - Table/Figure/Algorithm/Equation reference inventory (`Table 1`, `Figure 2`, `Algorithm 1`, etc.) with surrounding caption/narrative snippet and explicit visual-extraction limitation notice when underlying chart/table binary layout was not parsed visually.
       - Deterministic derived delta calculator (e.g., exact percentage-point differences between paired baseline/proposed values when both values are explicitly verified in text).
     - **Bounded Ollama Semantic Extraction (when Ollama available)**:
       - Instead of dumping an entire 160-page thesis into one prompt, selects a bounded section-balanced evidence packet (~6,000–7,500 chars max across Title/Abstract, Problem/Intro, Methodology/Dataset, Evaluation/Results, Conclusion/Limitations).
       - Requests strict JSON schema via `query_ollama_json`, parses with malformed-JSON tolerance (`extract_json_from_text`), validates fields, and preserves `"Not explicitly stated in the paper."` for missing items.
       - Cross-checks every Ollama claim against `DocumentChunk` evidence via `paper_evidence_service`; falls back cleanly to deterministic extraction whenever Ollama is offline, times out, or returns invalid JSON.

5. **`paper_analysis_service.py`**:
   - Orchestrates auth/ownership lookup, effective content assembly (`extracted_text`, chunks, handwritten manual edits if applicable), SHA-256 `content_hash` calculation, cache lookup (`ResearchPaperAnalysis`), invalidation on `content_hash` / `analysis_version` / manual classification override mismatch, execution timing instrumentation (`detection_ms`, `extraction_ms`, `llm_ms`, `total_ms`, `cache_retrieval_ms`), and DB persistence.

---

## 3. New Database Model (`backend/app/models/research_paper_analysis.py`)

Table: `research_paper_analyses` (idempotent `ensure_research_paper_analysis_schema(engine)` hook in `app/main.py` matching existing schema helpers):

- `id` (PK)
- `document_id` (`ForeignKey("documents.id", ondelete="CASCADE")`, indexed)
- `user_id` (`ForeignKey("users.id", ondelete="CASCADE")`, indexed)
- `content_hash` (`String(64)`, indexed)
- `analysis_version` (`String(32)`, default `"phase1_v1"`)
- `classification_override` (`String(32)`, nullable) — user manual override (`research_paper` / `non_research` / `None`)
- `status` (`String(32)`, `"completed"` | `"generating"` | `"failed"`)
- `analysis_mode` (`String(32)`, `"ollama_hybrid"` | `"deterministic_fallback"`)
- `paper_detection` (`JSON`)
- `basic_information` (`JSON`)
- `research_context` (`JSON`)
- `methodology` (`JSON`)
- `evaluation` (`JSON`)
- `conclusion` (`JSON`)
- `sections` (`JSON`)
- `numerical_data` (`JSON`)
- `tables_and_figures` (`JSON`)
- `evidence` (`JSON`)
- `timings` (`JSON`)
- `created_at` (`DateTime`)
- `updated_at` (`DateTime`)

---

## 4. API Design (`backend/app/api/routes/research_paper.py`)

Authenticated router under `/documents`:

1. `POST /documents/{document_id}/research-analysis`
   - Optional body (`ResearchAnalysisRequest`): `{ force_refresh: bool = False, classification_override: Optional["auto" | "research_paper" | "non_research"] = None, skip_llm: Optional[bool] = None }`.
   - Enforces JWT (`current_user`) + `Document.user_id == current_user.id` (`404` on nonexistent or unowned).
   - Checks cached row matching `(document_id, user_id, current_content_hash, ANALYSIS_VERSION)` and effective override; returns immediately with `cached=true` and `timings.cache_retrieval_ms`.
   - Otherwise computes, persists/updates `ResearchPaperAnalysis`, and returns `ResearchAnalysisResponse`.

2. `GET /documents/{document_id}/research-analysis`
   - Enforces JWT + ownership (`404` if doc absent or unowned, `404` if analysis not yet generated — with `outdated: bool` metadata if stored hash differs from current document hash).

Registered in `backend/app/main.py` after existing routers so zero existing endpoints change.

---

## 5. Analysis JSON Structure

Each response (`ResearchAnalysisResponse`) contains:
- Top-level: `document_id`, `document_filename`, `document_type`, `is_handwritten`, `content_hash`, `analysis_version`, `status`, `is_outdated`, `cached`, `analysis_mode`, `manual_override`, `pages_count`, `evidence_coverage`, `timings`.
- `paper_detection`: `{ is_research_paper, confidence, classification, manual_override, signals, missing_signals, rationale }`.
- Grounded item schema (`GroundedField` / `GroundedClaimItem`):
  - `value` / `claim`: extracted value or `"Not explicitly stated in the paper."`
  - `fact_type`: `"explicit" | "derived" | "inferred" | "missing"`
  - `evidence_ids`: list of matching `evidence[]` IDs (`ev-1`, `ev-2`, ...)
  - `sources`: inline source refs (`{ document_id, page, section, chunk_id, figure_or_table, excerpt, confidence }`)
- Structured domains:
  - `basic_information`: `title`, `authors`, `affiliation`, `abstract`, `keywords`, `publication_info`
  - `research_context`: `research_domain`, `problem_statement`, `motivation`, `research_objective`, `research_questions`, `hypothesis`
  - `methodology`: `methodology_type`, `proposed_approach`, `algorithms_models`, `architecture`, `framework_tools`, `dataset`, `dataset_size`, `preprocessing`, `experimental_setup`
  - `evaluation`: `evaluation_metrics`, `baseline_methods`, `experiments`, `results`, `numerical_findings`, `comparisons`
  - `conclusion`: `main_conclusions`, `limitations`, `future_work`
- `sections`: ordered tree/list with `id`, `title`, `normalized_role`, `level`, `page_start`, `page_end`, `chunk_ids`, `preview`.
- `numerical_data`: list of `{ metric_name, original_value, unit, experimental_context, fact_type, page, section, chunk_id, figure_or_table, excerpt, confidence }`.
- `tables_and_figures`: `{ items: [...], visual_parsing_limitation: "..." }`.
- `evidence`: normalized indexed map/list of verifiable evidence items referenced by claims & clickable in the UI.

---

## 6. Grounding Strategy

- **No fabrication rule**: Any field without supporting text returns `"Not explicitly stated in the paper."` with `fact_type: "missing"` and `sources: []`.
- **Excerpt verification**: Every extracted item must map to an actual `DocumentChunk` (using substring matching -> numeric/token overlap -> embedding similarity fallback) and store `document_id`, `page`, `section`, `chunk_id`, short verbatim `excerpt`, and `confidence`.
- **Fact classification**:
  - `explicit`: verbatim or directly paraphrased from an attributed chunk.
  - `derived`: deterministically computed deltas/totals from >=2 verified explicit numerical items.
  - `inferred`: minimal, explicitly labeled semantic categorization (e.g., coarse research domain when not named verbatim).

---

## 7. Caching & Versioning Strategy

- `content_hash = SHA-256` computed over: effective normalized text (`HandwrittenPage` edits prioritized if handwritten, else `Document.extracted_text`) + ordered chunk signature `(chunk_index, page_number)` + `classification_override`.
- `ANALYSIS_VERSION = "phase1_v1"`.
- Cache hit requires matching `(user_id, document_id, content_hash, analysis_version)`. Any document edit, re-OCR, manual transcription edit, or manual paper classification toggle updates hash/override and triggers recomputation cleanly.

---

## 8. Error Handling

- **Ollama offline / timeout / bad JSON**: Logs warning and transitions seamlessly to deterministic extraction (`analysis_mode = "deterministic_fallback"`), returning valid schema with explicit grounded extractions and empty-field fallbacks.
- **Empty / unreadable / nonstandard / handwritten docs**: Never crashes (`500`); returns low detection confidence with graceful explanations and preserved manual edits.
- **Missing `DocumentChunk` records**: Falls back cleanly to reconstructing synthetic page/text slices from `Document.extracted_text` (`page = 1` or page markers).

---

## 9. Security

- All `/documents/{id}/research-analysis` routes require `get_current_user` JWT dependency (`401` unauthenticated).
- Queries filter strictly by `(Document.id == document_id, Document.user_id == current_user.id)` and `(ResearchPaperAnalysis.document_id == document_id, ResearchPaperAnalysis.user_id == current_user.id)`.
- Nonexistent and cross-tenant documents both return HTTP `404` with zero existence or metadata leakage.

---

## 10. Performance Considerations

- CPU-compatible local execution:
  - Sectioning, detector scoring, and regex/numeric extraction execute deterministically in `< 50 ms` for typical PDFs and `< 300 ms` even for 160-page theses.
  - Only a section-representative evidence budget (`<= 7,500` chars) is sent to Ollama, avoiding full-paper prompt overflow or multi-minute CPU timeouts on 100+ page documents.
  - Cached repeat requests serve directly from SQLite JSON in `< 15 ms`.

