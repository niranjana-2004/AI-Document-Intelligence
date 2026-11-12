# Cognidocs — Research Paper Analyzer (Phase 1) Verification Report

## 1. Phase 1 Architecture Summary

Phase 1 delivers **Source-Grounded Structured Research Paper Analysis** integrated directly into Cognidocs' existing FastAPI + SQLAlchemy + React architecture without introducing a separate RAG stack, cloud dependency, or Phase 2 critical-grading/literature-synthesis scope creep.

### Reused Cognidocs Infrastructure
- **Storage & Chunks**: `Document` (`backend/app/models/document.py`), `DocumentChunk` (`page_number`, `chunk_index`, `content`, `embedding`, `category`), and `HandwrittenPage` (`edited_transcription` prioritized over `raw_transcription`).
- **Embeddings & Similarity**: Existing cached MiniLM singleton (`app.services.embedding_services.generate_embedding`) and `app.services.similarity_service.cosine_similarity`.
- **Local LLM Client**: Existing `app.services.handwriting.ollama_client.query_ollama_json` / `extract_json_from_text` (`llama3.2` on `http://127.0.0.1:11434`).
- **Authentication & Tenant Isolation**: `app.api.dependencies.get_current_user` (JWT) + strict ownership checks (`Document.id == document_id`, `Document.user_id == current_user.id`).
- **Frontend Styling & Deep-Linking**: Global CSS theme variables (`frontend/src/index.css`) and `buildSourceNavigationUrl` (`frontend/src/utils/citationUtils.js`) linking directly into `/documents?doc=...&page=...&highlight=...` and `/handwritten/{id}?page=...&highlight=...`.

### Architecture Design Document
- Design specification authored prior to implementation: [`research_paper_analyzer_phase1_design.md`](file:///d:/AI-Document-Intelligence/backend/benchmarks/research_paper_analyzer_phase1_design.md)

---

## 2. Backend Implementation Overview

| Component | Path | Responsibility |
|---|---|---|
| SQLAlchemy Cache Model | `backend/app/models/research_paper_analysis.py` | `ResearchPaperAnalysis` table (`research_paper_analyses`) + `ensure_research_paper_analysis_schema()`, keyed by `(document_id, user_id, content_hash, analysis_version, classification_override)` |
| Pydantic API Contract | `backend/app/schemas/research_paper.py` | `ResearchAnalysisRequest`, `ResearchAnalysisResponse`, `GroundedField`, `PaperDetectionResult`, `SectionNode`, `NumericalFinding`, `TablesAndFiguresSummary`, `EvidenceItem`, `MISSING_FIELD_TEXT = "Not explicitly stated in the paper."` |
| Content-Based Detector | `backend/app/services/research/paper_detector.py` | Multi-signal academic detection (sections, DOI/ISSN/venue, citations, visual refs, author-email block, non-academic CV/invoice counter-signals) + manual override (`auto` / `research_paper` / `non_research`) |
| Section Hierarchy Service | `backend/app/services/research/paper_section_service.py` | Reconstructs ordered `ChunkUnit` records, detects numbered/Roman/standalone headings, builds hierarchical `SectionNode` tree, filters dotted ToC lines (`..... 66`) and running headers |
| Evidence Grounding Service | `backend/app/services/research/paper_evidence_service.py` | Verifies every populated claim/metric against `DocumentChunk` records, records verbatim excerpt, page, section, chunk ID, figure/table label, and `evidence_coverage` |
| Structured Extractor | `backend/app/services/research/paper_extraction_service.py` | Deterministic extraction + optional bounded Ollama JSON extraction with strict anti-hallucination verification and automatic fallback |
| Orchestration & Caching | `backend/app/services/research/paper_analysis_service.py` | SHA-256 `content_hash` computation, invalidation on document edit/re-OCR/override, timing telemetry, and persistence |
| API Router | `backend/app/api/routes/research_paper.py` | `POST /documents/{document_id}/research-analysis` & `GET /documents/{document_id}/research-analysis`, registered in `backend/app/main.py` |

---

## 3. Real-Document Validation Results (Tests A–E + Safety & Security)

Executed via [`run_research_paper_validation.py`](file:///d:/AI-Document-Intelligence/backend/benchmarks/run_research_paper_validation.py) inside `isolated_test_db(clone_dev_db=True)` (cloned read-only from `documents.db` into temporary SQLite storage). Raw metrics saved in [`research_paper_analyzer_phase1_results.json`](file:///d:/AI-Document-Intelligence/backend/benchmarks/research_paper_analyzer_phase1_results.json).

| Scenario | Real Cognidocs Document | Pages | Classification (Score) | Populated / Grounded Fields | Sections | Num. Data / Table-Fig Refs | Latency / Cache Hit |
|---|---|---:|---|---|---|---|---|
| **Test A (Academic PDF, deterministic)** | `Fortifying+Cloud+Security+with+Advanced+Data+Encryption+Technique.pdf` (`id=2`, PDF) | 8 | `research_paper` (`0.99`, 12 signals) | `23 / 23` (`coverage=1.0`, `7` missing) | `15` | `0` metrics / `3` figs (`Figure 1–3`) | `473.58 ms` (`repeat POST: 34.81 ms`, `GET: 31.04 ms`) |
| **Test A (Live Ollama `llama3.2` hybrid)** | Same (`id=2`) with `skip_llm=False` | 8 | `research_paper` (`0.99`) | `23 / 23` (`coverage=1.0`) | `15` | `3` figs | `35,314.51 ms` (`llm_ms=35,011.81` -> timeout fallback to `deterministic_fallback`, status `200 OK`) |
| **Test B (Non-Research PDF)** | `Niranjana A S_Resume.pdf` (`id=1`, PDF) | 2 | `non_research` (`0.02`, 0 signals) | `7 / 7` (`coverage=1.0`, `23` missing) | `0` | `0` / `0` | `93.37 ms` (`repeat POST: 18.29 ms`, `GET: 17.98 ms`) |
| **Test C (Technical Report DOCX)** | `Project Report - LLM.docx` (`id=3`, DOCX) | 1 | `borderline_technical` (`0.50`) | `19 / 19` (`coverage=1.0`, `11` missing) | `12` | `8` sample/dataset metrics | `352.04 ms` (`repeat POST: 30.08 ms`, `GET: 31.27 ms`) |
| **Test C (Manual Override)** | Same (`id=3`, `classification_override="research_paper"`) | 1 | `research_paper` (`is_research_paper=True`, score `0.50`) | `19` populated | `12` | — | HTTP `200 OK` |
| **Test E (Long Academic Thesis)** | `Subhabrata Rana - Thesis.pdf` (`id=5`, PDF) | 160 | `research_paper` (`0.99`) | `27 / 27` (`coverage=1.0`) | `96` | `1` metric (`30,000 records`, p.99) / `30` table/fig refs | `1,518.25 ms` (`repeat POST: 175.96 ms`, `GET: 172.81 ms`) |
| **Handwritten PDF Safety** | `text-to-handwriting.pdf` (`id=12`, HANDWRITTEN) | 7 | `non_research` (`0.02`) | `6 / 6` (`coverage=1.0`, `24` missing) | `12` | `0` / `0` | `198.89 ms` (`repeat POST: 25.28 ms`, `GET: 17.61 ms`) |

### Security & Dev Database Isolation Checks
- Unauthenticated `GET /documents/2/research-analysis`: **`401 Unauthorized`**.
- Cross-tenant `POST /documents/2/research-analysis` (user `4` accessing user `1` document): **`404 Not Found`**.
- Production SQLite integrity (`backend/documents.db`): **`102` documents and `102` conversations before and after** (0 mutations).

---

## 4. Frontend Implementation

### New & Updated Files
- **API helpers**: `analyzeResearchPaper`, `getResearchPaperAnalysis` in [`api.js`](file:///d:/AI-Document-Intelligence/frontend/src/services/api.js)
- **Workspace Page**: [`ResearchPaperAnalyzer.jsx`](file:///d:/AI-Document-Intelligence/frontend/src/components/research/ResearchPaperAnalyzer.jsx) — document selector (`?doc=` deep-link support), deterministic toggle, re-analyze trigger, classification override, tabs (*Context & Methodology*, *Evaluation & Metrics*, *Sections & Figures*), numerical findings table with units/fact types, section outline tree, and explicit visual-parsing limitation banner.
- **Overview & Section Cards**: [`PaperOverview.jsx`](file:///d:/AI-Document-Intelligence/frontend/src/components/research/PaperOverview.jsx) & [`PaperSectionCard.jsx`](file:///d:/AI-Document-Intelligence/frontend/src/components/research/PaperSectionCard.jsx)
- **Interactive Evidence Drawer**: [`EvidenceDrawer.jsx`](file:///d:/AI-Document-Intelligence/frontend/src/components/research/EvidenceDrawer.jsx) — claim provenance viewer + searchable evidence index with one-click navigation via `buildSourceNavigationUrl`.
- **Theme-Aware Styles**: [`research-paper.css`](file:///d:/AI-Document-Intelligence/frontend/src/styles/research-paper.css) using CSS custom properties from `frontend/src/index.css`.
- **UI Helpers & Tests**: [`researchPaperUtils.js`](file:///d:/AI-Document-Intelligence/frontend/src/utils/researchPaperUtils.js) & [`researchPaperUtils.test.mjs`](file:///d:/AI-Document-Intelligence/frontend/src/utils/researchPaperUtils.test.mjs)
- **Routing & Entry Points**: Protected `/research-analyzer` route in [`App.jsx`](file:///d:/AI-Document-Intelligence/frontend/src/App.jsx), sidebar link in [`AppLayout.jsx`](file:///d:/AI-Document-Intelligence/frontend/src/layouts/AppLayout.jsx), and `Analyze Paper` card action in [`Documents.jsx`](file:///d:/AI-Document-Intelligence/frontend/src/pages/Documents.jsx).

---

## 5. Verification & Regression Suite Summary

All checks ran cleanly after final edits:

1. **New Backend Feature Tests (`tests.test_research_paper_analyzer`)**: **`20 / 20` PASS (`OK` in `27.211s`)**
   - Covers high-confidence paper detection, non-research filename-spoofing rejection, borderline technical doc + manual override persistence, title/author/abstract/methodology/dataset/metric grounding, ToC dotted-line filtering, `evidence_coverage`, missing-field honesty (`"Not explicitly stated in the paper."`), Ollama offline fallback, malformed JSON & ungrounded LLM claim rejection, repeat POST/GET caching, SHA-256 `content_hash` invalidation on edits, JWT + cross-tenant isolation, numerical units + derived deltas, table/figure/algorithm/equation indexing, and handwritten + empty document safety.
2. **Combined Backend Regression Run**: **`99 / 99` PASS (`OK` in `88.345s`)**
   - Modules verified together: `tests.test_research_paper_analyzer`, `tests.test_grounded_citations`, `tests.test_search_service`, `tests.test_voice_assistant`, `tests.test_voice_query_recovery`, `tests.test_layout_intelligence`, `tests.test_ocr35_recovery`, `tests.test_layout_guided_ocr_phase_b`.
3. **Frontend Unit Tests (`node --test`)**: **`12 / 12` PASS (`0` failed, `0` skipped in `111.95 ms`)**
   - Covers `researchPaperUtils.test.mjs`, `citationUtils.test.mjs`, and `voiceUtils.test.mjs`.
4. **ESLint (targeted new & modified frontend files)**: **`0` errors, `0` warnings**.
5. **Vite Production Build (`npm run build`)**: **PASS** (`2515` modules transformed, built in `759 ms`).

---

## 6. Observed Limitations & Phase 1 Boundaries

- **Visual Figure / Chart Parsing Not Performed**: As surfaced explicitly in `tables_and_figures.visual_parsing_limitation` and the frontend UI banner, Phase 1 indexes numbered references and captions from extracted text only; embedded plot values and complex visual table grids remain out of scope for Phase 1.
- **CPU Local Ollama Timeout Fallback Verified**: With `ollama serve` active (`llama3.2:latest`) on CPU, Test A's cold LLM call hit the `35s` request budget (`llm_ms=35,011.81`) and cleanly fell back to deterministic extraction without error or ungrounded text.
- **Real-Document Spaced-Dot ToC Nuance**: While triple-dot ToC leaders (`..... 66`) are filtered cleanly in unit tests and section trees, Page 11 of `Subhabrata Rana - Thesis.pdf` formats sub-entries with single spaced periods (`"30 3.1 KMSs Supporting Ceph... . 34 3.2 ..."`), allowing those ToC lines to surface as candidate evidence for `limitations` / `future_work` when deterministic keyword matching scans early front-matter pages.
- **Scope Exclusions Preserved**: Phase 2 capabilities (critical paper grading, peer review, research-gap generation, multi-paper synthesis, web search, plagiarism detection, knowledge graphs) were intentionally excluded.

