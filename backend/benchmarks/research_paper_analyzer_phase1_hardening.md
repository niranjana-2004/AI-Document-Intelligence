# Research Paper Analyzer — Phase 1 Hardening & Edge-Case Validation Report

## 1. Executive Summary

A controlled **Phase 1 Hardening + Edge-Case Validation Pass** was completed for the Cognidocs Research Paper Analyzer without modifying or adding Phase 2 features, external research APIs, or cloud LLM dependencies.

Key measurable hardening outcomes observed in this validation pass:

- **Bounded Ollama Hybrid Stability**: Compressing Ollama evidence packets (`MAX_LLM_CONTEXT_CHARS = 3600`), deduplicating repeated running headers/footers across pages, stripping Table-of-Contents (ToC) noise, prioritizing core sections, and bounding Ollama CPU options (`num_ctx = 4096`, `num_predict = 550`, `timeout = 35`) converted the pre-hardening live local CPU `llama3.2` timeout on Document `#2` (`35,011.81 ms` -> `deterministic_fallback`) into a completed **`ollama_hybrid`** extraction in **`24,389.61 ms` LLM / `24,861.05 ms` total** with `23/23` grounded fields (`evidence_coverage = 1.0`), while preserving graceful `deterministic_fallback` on timeout/malformed/empty responses (`tests 13, 17, 22, 23`).
- **Zero ToC False Positives Across 14 Evaluation Runs**: Hardening `is_toc_line` / `is_toc_chunk` and filtering ToC chunks out of `basic_information` (`front_units`, `abs_units`), sentence extraction, numerical parsing, and visual reference scanning reduced `toc_false_positive_count` to **`0`** across all `7` real-document runs and `7` synthetic edge-case fixtures (including collapsed multi-entry thesis ToC fragments on `Subhabrata Rana - Thesis.pdf` (`doc #5`, `160` pages), which shifted from `27` populated fields pre-hardening to `26` clean grounded fields post-hardening).
- **Zero Structural-Number & Visual-Claim False Positives**: Masking `Section X.Y`, `Figure N`, `Table N`, `Eq. (N)`, `[18]`, `Page N`, and publication years `19xx`/`20xx` prevented structural/year leakage into `numerical_data` (`structural_number_false_positive_count = 0`) while supporting sub-figures (`Figure 3(a)`), Roman-numeral tables (`Table II`), equations (`Eq. (4)` -> normalized `Equation (4)`), algorithms, p-values, confidence intervals, decimals, and multi-metric comparison deltas without claiming visual chart pixel parsing (`unsupported_visual_claim_count = 0`).
- **Zero Evidence Navigation Mismatches**: Audited `wrong_evidence_navigation_count = 0` across all `14` benchmark runs; printed sources target `/documents?doc=<id>&page=<n>` and handwritten sources target `/handwritten/<id>?page=<n>`.
- **Full Regression & DB Safety**: All `37/37` Research Paper Analyzer tests (`42.159s`), `116/116` combined unittest regression tests across `8` suites (`73.842s`), `18/18` Multi-Document Chat, `10/10` Document Comparison, `10/10` Mind Map, isolated handwritten Phase 3 Intelligence + `10`-step Advanced Quiz/Flashcard checks, `13/13` frontend Node unit tests (`159.65ms`), targeted ESLint (`0` errors), and Vite production build all passed after hardening with `backend/documents.db` unchanged (`102` documents, `102` conversations, `1` cached research analysis row pre-existing).

---

## 2. Hardening Baseline Before Changes

Pre-hardening baseline captured prior to edits:

- **Dev Database**: `backend/documents.db` held `102` documents, `102` conversations, `1` row in `research_paper_analyses` (pre-existing under `analysis_version = "phase1_v1"`).
- **Pre-Hardening Tests**: `20/20` Research Paper tests (`27.211s`), `99/99` 8-suite backend regression (`88.345s`).
- **Observed Weaknesses in Pre-Hardening Real-Document Results (`research_paper_analyzer_phase1_results.json`)**:
  1. **Live Ollama CPU Timeout**: `doc #2` timed out at `35,011.81 ms` when sending a ~`7000`-char evidence packet with default `num_ctx = 8192`, forcing fallback.
  2. **ToC Leakage**: Collapsed multi-entry spaced-dot ToC fragments on Document `#5` (`Subhabrata Rana - Thesis.pdf`, Page 11) leaked into extracted text (`"30 3.1 ... . 34 3.2 ..."`).
  3. **Structural Number Ambiguity**: Decimal structural references such as `Section 3.2` could sit adjacent to result percentages (`92.4%`) without explicit structural masking.
  4. **Handwritten Safeguard Gap**: No hard `is_handwritten` confidence ceiling existed in `detect_research_paper` if scanned handwritten lecture notes happened to mention `"Abstract"`, `"Methodology"`, or `"References"`.
  5. **Sentence Split Breakage**: `re.split(r"(?<=[.!?])\s+")` split mid-citation on `Fig.` / `Eq.`, breaking `Eq. (4)` and multi-metric comparison sentences containing decimals (`Precision = 97.4%, Recall = 96.1%...`).

---

## 3. Hardening Changes Implemented

### Backend

- [`ollama_client.py`](file:///d:/AI-Document-Intelligence/backend/app/services/handwriting/ollama_client.py): Added optional backwards-compatible `num_ctx: Optional[int] = None` and `num_predict: Optional[int] = None` parameters to `query_ollama` and `query_ollama_json` so Research Paper Analyzer can pass bounded inference options (`num_ctx=4096`, `num_predict=550`) without altering existing callers (`8192` default preserved).
- [`paper_section_service.py`](file:///d:/AI-Document-Intelligence/backend/app/services/research/paper_section_service.py):
  - Added public `is_toc_line(line, in_toc_block=False)` and `is_toc_chunk(text)` filters rejecting dotted/spaced-dot ToC leaders (`. . .`), Roman/Arabic ToC page entries, collapsed multi-entry ToC fragments, and IEEE/ACM copyright/grant footnotes.
  - Added support for `References`, `CCS CONCEPTS`, and lettered IEEE subsections (`A. Threat Model` at hierarchy level `2`).
- [`paper_detector.py`](file:///d:/AI-Document-Intelligence/backend/app/services/research/paper_detector.py):
  - Added `is_handwritten: bool = False` safeguard clamping detection confidence to `<= 0.30` (`non_research`) unless overridden (`manual_override == "research_paper"`).
  - Expanded non-academic counter-signals (`assignment`, `homework`, `course syllabus`, `lecture notes`, `quarterly revenue`, `api reference`, `installation guide`, `user manual`) and IEEE/ACM/DOI/Roman/subfigure signals.
- [`paper_analysis_service.py`](file:///d:/AI-Document-Intelligence/backend/app/services/research/paper_analysis_service.py):
  - Passed `is_handwritten=bool(document.is_handwritten)` into `detect_research_paper`.
  - Bumped `RESEARCH_ANALYSIS_VERSION` from `"phase1_v1"` to `"phase1_v1_hardened"` so any pre-hardening cached rows cleanly recompute on access (`is_outdated` invalidation).
- [`paper_evidence_service.py`](file:///d:/AI-Document-Intelligence/backend/app/services/research/paper_evidence_service.py):
  - Upgraded `detect_figure_or_table_in_text` to match sub-figures (`Figure 3(a)`, `Fig. 2(a)`), uppercase Roman tables (`Table II`), equations (`Eq. (4)`, `Equation 5`), and algorithms while avoiding false matches on lowercase words.
- [`paper_extraction_service.py`](file:///d:/AI-Document-Intelligence/backend/app/services/research/paper_extraction_service.py):
  - Added `MAX_LLM_CONTEXT_CHARS = 3600`, `_normalize_header_key`, `_clean_text_for_llm`, and `_select_bounded_evidence_packet` (strips repeated running headers/footers across `>= 2` pages with normalized page numbers, ToC lines, duplicate chunks; orders context `front/abstract -> introduction -> methodology -> experiments -> results -> conclusion -> other`).
  - Passed compact non-fabricating JSON prompt + `num_ctx=4096, num_predict=550, timeout=35` to `query_ollama_json`.
  - Added shared `_split_sentences` helper shielding `Fig.`, `Eq.`, `Sec.`, `Ref.`, `Vol.`, `No.`, `Dr.`, `Prof.`, `vs.`, `et al.` across field extraction, numerical parsing, and figure/table extraction.
  - Excluded ToC chunks from `basic_information` (`front_units`, `abs_units`), `_first_sentences`, `_find_evidence_in_units`, `_extract_numerical_data`, and `_extract_tables_and_figures`.
  - Added `_mask_structural_numbers` to exclude structural/year traps (`Section 3.2`, `Figure 4`, `Table 2`, `Eq. (5)`, `Page 12`, `[18]`, `2024`); generalized multi-metric comparison deltas (`Accuracy`, `Precision`, `Recall`, `F1-score`) allowing decimal intermediate values; added p-values, confidence intervals, and decimal metrics (`0.91`).
  - Added IEEE/ACM comma-separated author block fallback and normalized `Fig.` -> `Figure`, `Eq.` -> `Equation`.

### Frontend & Verification

- [`researchPaperUtils.test.mjs`](file:///d:/AI-Document-Intelligence/frontend/src/utils/researchPaperUtils.test.mjs): Added coverage for borderline classification badge metadata, manual `non_research` override state, and missing-field fallback metadata.
- [`test_research_paper_analyzer.py`](file:///d:/AI-Document-Intelligence/backend/tests/test_research_paper_analyzer.py): Expanded from `20` to `37` tests (`tests 21-37` covering Objectives A-K).
- [`research_paper_hardening_manifest.json`](file:///d:/AI-Document-Intelligence/backend/benchmarks/research_paper_hardening_manifest.json) & [`run_research_paper_hardening.py`](file:///d:/AI-Document-Intelligence/backend/benchmarks/run_research_paper_hardening.py): Added 14-category hardening manifest and isolated validation runner generating [`research_paper_hardening_results.json`](file:///d:/AI-Document-Intelligence/backend/benchmarks/research_paper_hardening_results.json).

---

## 4. Controlled Edge-Case Test Corpus

Strict separation of corpus origins:

| Category | Origin | Source / Fixture | Expected Behavior |
|---|---|---|---|
| `standard_academic` / `journal` | **Real Cognidocs DB** | `doc #2`: `Fortifying+Cloud+Security+with+Advanced+Data+Encryption+Technique.pdf` (8 pages) | Classified `research_paper` |
| `thesis` / `toc_heavy` (real) | **Real Cognidocs DB** | `doc #5`: `Subhabrata Rana - Thesis.pdf` (160 pages) | Classified `research_paper`, zero ToC leakage |
| `resume` | **Real Cognidocs DB** | `doc #1`: `Niranjana A S_Resume.pdf` (2 pages) | Rejected (`non_research`) |
| `technical_report` / `project_report` | **Real Cognidocs DB** | `doc #3`: `Project Report - LLM.docx` | `borderline_technical` -> manual override `research_paper` |
| `handwritten_notes` | **Real Cognidocs DB** | `doc #12`: `text-to-handwriting.pdf` (7 pages) | Rejected (`non_research`), routes `/handwritten/{id}` |
| `ieee_two_column` | **Synthetic Hardening Fixture** | `synthetic_ieee_packetguard.pdf` | Roman/lettered headings, IEEE authors, metric comparison delta |
| `acm_style` | **Synthetic Hardening Fixture** | `synthetic_acm_verisql.pdf` | ACM venue, `CCS CONCEPTS`, `Keywords`, `p < 0.01` |
| `toc_heavy` + structural traps | **Synthetic Hardening Fixture** | `synthetic_toc_traps_paper.pdf` | Zero ToC leaks, zero structural-number leaks |
| `missing_fields` | **Synthetic Hardening Fixture** | `synthetic_minimal_paper.pdf` | Strict `"Not explicitly stated in the paper."` |
| Student assignment | **Synthetic Hardening Fixture** | `cs401_assignment3.pdf` | Rejected (`non_research`) |
| Product/business doc | **Synthetic Hardening Fixture** | `enterprise_gateway_manual.pdf` | Rejected (`non_research`) |
| Handwritten note w/ academic terms | **Synthetic Hardening Fixture** | `lecture_notes_scan.png` (`is_handwritten=True`) | Clamped `confidence <= 0.30` (`non_research`) |

> **Gap Disclosure**: No real IEEE two-column PDF or ACM proceedings PDF currently exists in `backend/documents.db`. IEEE two-column and ACM formatting were validated via **synthetic hardening fixtures**, not real third-party IEEE/ACM PDF extractions.

---

## 5. Ollama Stability & Context Bounding Validation

- **Configured Bounds**: `MAX_LLM_CONTEXT_CHARS = 3600`, `num_ctx = 4096`, `num_predict = 550`, `timeout = 35` (`llama3.2:latest`).
- **Unit & API Failure Resilience**:
  - `test_21`: Verified packet truncation `<= 3600` chars, removal of page-numbered running footers/headers across pages, removal of ToC dot-leader chunks, and section ordering (`Abstract` before `Experiments and Results`).
  - `test_22`: Verified simulated 35s Ollama timeout triggers clean fallback (`analysis_mode = "deterministic_fallback"`, HTTP 200) and asserts `timeout == 35`, `num_ctx <= 4096`, `num_predict <= 600`.
  - `test_23` & `test_17`: Verified empty `{}` and malformed/ungrounded LLM JSON fall back safely without fabricated claims.
- **Live Local Ollama Observation (`doc #2`, `llama3.2:latest`)**:
  - Pre-hardening (`num_ctx = 8192`, ~`7000`-char packet): Timed out at `35,011.81 ms` -> `deterministic_fallback`.
  - Post-hardening (`3600`-char bounded packet, `num_ctx = 4096`, `num_predict = 550`): Completed live **`ollama_hybrid`** extraction in **`24,389.61 ms` LLM (`24,861.05 ms` total / `24,882.87 ms` wall)** with `23/23` populated fields grounded (`evidence_coverage = 1.0`, `sections_count = 16`, `tables_and_figures = 3`).

---

## 6. ToC & Noise Filtering Validation

- Tested real 160-page thesis (`doc #5`: `Subhabrata Rana - Thesis.pdf`) AND synthetic leading/collapsed ToC fixtures (`test_24`, `test_34`, `synthetic_toc_traps_paper.pdf`):
  - **Before hardening**: Collapsed multi-entry ToC fragments on `doc #5` leaked into `27` populated fields.
  - **After hardening**: Fresh `phase1_v1_hardened` extraction on `doc #5` produced `26` populated fields (`26/26` grounded), `86` real sections, `30` tables/figures, and **`0`** ToC leaks in `sections`, `evidence`, or extracted claim fields.
  - **Aggregate**: `toc_false_positive_count = 0` across all `14` benchmark runs (`0/7` real, `0/7` synthetic).

---

## 7. Numerical & Metric Extraction Safety Validation

- **Unit & Mocked Validation (`test_27`, `test_25`, `test_18`)**:
  - Verified structural references and years (`Section 3.2`, `Figure 4`, `Table 2`, `Eq. (5)`, `Page 12`, `[18]`, `2024`) were excluded from `numerical_data`.
  - Verified extraction of `87.2%` Accuracy, `0.91` F1-score, `p < 0.05`, `95% CI [0.88, 0.94]`, latency `ms`, sample counts, and paired `Precision` comparison delta (`+8.9 percentage points` between `97.4%` and `88.5%`).
- **Benchmark Safety Counter**: `structural_number_false_positive_count = 0` across all `14` runs (`real_documents` + `synthetic_fixtures`).

---

## 8. Missing-Information Honesty & Groundedness Validation

- Every missing field across minimal synthetic papers (`test_28`, `synthetic_minimal_missing_fields`) and non-research/incomplete documents returned the exact canonical marker **`"Not explicitly stated in the paper."`** with `fact_type = "missing"` and `0` invented sources.
- Across ALL `14` benchmark runs (`7` real + `7` synthetic), every populated field had valid source citations (`evidence_coverage = 1.0` on every evaluated document/fixture: `23/23` `doc #2`, `26/26` `doc #5`, `19/19` `doc #3`, `7/7` `doc #1`, `6/6` `doc #12`, `16/16` IEEE, `11/11` ACM, `13/13` ToC/traps, `6/6` minimal).

---

## 9. Figure, Table, Algorithm & Equation Validation

- Regex and sentence-splitter hardening (`_split_sentences` shielding `Fig.` / `Eq.`) validated on `test_29`, `test_19`, and `synthetic_toc_traps_paper.pdf`:
  - Matches `Figure 1`, `Fig. 2(a)` (normalized `Figure 2(a)`), `Figure 3(a)`, `Table 1`, `Table II`, `Algorithm 1`/`2`, `Equation 1`/`(4)` (`Eq. (4)` -> `Equation (4)`).
  - Extracted visual references on real corpus: `doc #2` (`3` items: `Figure 1`, `Figure 2`, `Figure 3`), `doc #5` (`30` items e.g. `Figure 2.1`, `Table 2.1`, ...).
- `unsupported_visual_claim_count = 0` across all `14` runs (`visually_parsed: false` enforced on every entry alongside explicit `visual_parsing_limitation` notice).

---

## 10. Detection & Classification Precision Validation

| Document / Fixture | Origin | `is_research_paper` | `classification` | `confidence` | Outcome |
|---|---|---|---|---|---|
| `doc #2` Journal PDF | Real DB | `true` | `research_paper` | `0.99` | Accurate |
| `doc #2` (Live Ollama) | Real DB | `true` | `research_paper` | `0.99` | Accurate |
| `doc #5` Thesis (160p) | Real DB | `true` | `research_paper` | `0.99` | Accurate |
| `doc #1` Resume PDF | Real DB | `false` | `non_research` | `0.02` | Accurate |
| `doc #3` Project DOCX | Real DB | `false` | `borderline_technical` | `0.50` | Accurate |
| `doc #3` (Override) | Real DB | `true` | `research_paper` | `0.50` | Override honored |
| `doc #12` Handwritten PDF | Real DB | `false` | `non_research` | `0.02` | Accurate |
| `synthetic_ieee_packetguard` | Synthetic | `true` | `research_paper` | `0.99` | Accurate |
| `synthetic_acm_verisql` | Synthetic | `true` | `research_paper` | `0.99` | Accurate |
| `synthetic_toc_traps_paper` | Synthetic | `true` | `research_paper` | `0.99` | Accurate |
| `synthetic_minimal_paper` | Synthetic | `true` | `research_paper` | `0.65` | Accurate |
| `cs401_assignment3` | Synthetic | `false` | `non_research` | `0.02` | Accurate |
| `enterprise_gateway_manual` | Synthetic | `false` | `non_research` | `0.02` | Accurate |
| `lecture_notes_scan.png` (HW) | Synthetic | `false` | `non_research` | `0.14` | Handwritten clamp active |

---

## 11. Caching & Invalidation Validation

- Verified repeat `POST /documents/{id}/research-analysis` (`force_refresh=False`) returns `cached = True` cleanly:
  - `doc #2`: `17.90 ms`
  - `doc #1`: `11.53 ms`
  - `doc #3`: `12.17 ms`
  - `doc #5` (160 pages): `95.36 ms`
  - `doc #12`: `9.98 ms`
- Verified `RESEARCH_ANALYSIS_VERSION = "phase1_v1_hardened"` forces invalidation (`is_outdated = True`) on pre-hardening `phase1_v1` cache entries, and content hash changes upon edited handwritten transcriptions or updated chunks (`test_15`, `test_20`).
- Verified `non_research` manual override persists cleanly across subsequent cached `GET` requests (`test_36`).

---

## 12. Real-Document Benchmark Summary

Real Cognidocs DB timing & extraction breakdown (`skip_llm=True` deterministic vs `skip_llm=False` live Ollama, `isolated_test_db(clone_dev_db=True)`):

| Run | Mode | `detection_ms` | `extraction_ms` | `llm_ms` | `total_ms` | Wall (`ms`) | Sections | Populated / Grounded |
|---|---|---|---|---|---|---|---|---|
| `doc #2` (`8p` journal) | `deterministic_fallback` | `30.43` | `447.51` | `0.00` | `494.72` | `570.72` | `16` | `23 / 23` |
| `doc #2` (`8p` journal) | `ollama_hybrid` | `23.84` | `425.14` | `24389.61` | `24861.05` | `24882.87` | `16` | `23 / 23` |
| `doc #1` (`2p` resume) | `deterministic_fallback` | `4.72` | `76.59` | `0.00` | `85.70` | `98.31` | `0` | `7 / 7` |
| `doc #3` (DOCX report) | `deterministic_fallback` | `11.25` | `255.64` | `0.00` | `272.06` | `285.78` | `12` | `19 / 19` |
| `doc #3` (Manual override) | `deterministic_fallback` | `10.63` | `259.68` | `0.00` | `275.94` | `289.09` | `12` | `19 / 19` |
| `doc #5` (`160p` thesis) | `deterministic_fallback` | `193.83` | `2089.79` | `0.00` | `2376.09` | `2394.57` | `86` | `26 / 26` |
| `doc #12` (`7p` handwritten) | `deterministic_fallback` | `5.34` | `160.61` | `0.00` | `169.17` | `182.40` | `12` | `6 / 6` |

---

## 13. Frontend & Integration Validation

- **Frontend Unit Tests (`node --test src/utils/*.test.mjs`)**: **`13 / 13` passed** (`159.65 ms`), covering `researchPaperUtils` (fact-type pills, detection/override badges, section flattening, evidence filtering, missing-field metadata), `citationUtils` (`/handwritten/{id}?page=...` vs `/documents?doc={id}&page=...` routing), and `voiceUtils`.
- **Frontend Targeted ESLint**: `0` errors and `0` warnings across [`src/components/research`](file:///d:/AI-Document-Intelligence/frontend/src/components/research/ResearchPaperAnalyzer.jsx), [`researchPaperUtils.js`](file:///d:/AI-Document-Intelligence/frontend/src/utils/researchPaperUtils.js), [`researchPaperUtils.test.mjs`](file:///d:/AI-Document-Intelligence/frontend/src/utils/researchPaperUtils.test.mjs), [`Documents.jsx`](file:///d:/AI-Document-Intelligence/frontend/src/pages/Documents.jsx), [`citationUtils.js`](file:///d:/AI-Document-Intelligence/frontend/src/utils/citationUtils.js), and [`citationUtils.test.mjs`](file:///d:/AI-Document-Intelligence/frontend/src/utils/citationUtils.test.mjs). *(Note: global `npm run lint` reports `48` errors / `16` warnings pre-existing in unrelated legacy handwritten/voice components such as `AIHealthIndicator.jsx`, untouched by Phase 1 hardening.)*
- **Vite Production Build (`npm run build`)**: **PASS** (`2515` modules transformed, clean bundle generated).
- **Live Browser Click-Through Disclosure**: Interactive Chrome DevTools click-through (Cases 1–6) did **not** execute in this session because Chrome remote debugging (`DevToolsActivePort`) was unavailable and Playwright is not installed in the workspace. API contracts and evidence navigation URL builders backing Cases 1–6 (`doc #2`, `#1`, `#3` + override, missing fields, `doc #12` handwritten routing, and `doc #5` 160-page thesis hierarchy) were directly verified via backend `TestClient` and frontend unit tests.

---

## 14. Full Regression Verification

All suites ran against in-memory or `isolated_test_db` temporary SQLite snapshots (zero dev DB pollution):

- **Research Paper Analyzer (`tests.test_research_paper_analyzer`)**: **`37 / 37` OK** (`42.159s`)
- **8-Suite Backend Regression**: **`116 / 116` OK** (`73.842s`) covering:
  - `tests.test_research_paper_analyzer` (`37`)
  - `tests.test_grounded_citations`
  - `tests.test_search_service`
  - `tests.test_voice_assistant`
  - `tests.test_voice_query_recovery`
  - `tests.test_layout_intelligence`
  - `tests.test_ocr35_recovery`
  - `tests.test_layout_guided_ocr_phase_b` (`16`)
- **Multi-Document Chat (`test_multi_document_chat.py`)**: **`18 / 18` PASS** (`isolated_test_db`)
- **Document Comparison (`test_document_comparison.py`)**: **`10 / 10` PASS** (`isolated_test_db`)
- **Mind Map Generator (`test_document_mind_map.py`)**: **`10 / 10` PASS** (`isolated_test_db`)
- **Handwritten Phase 3 Intelligence (`test_phase3_intelligence.py` in `isolated_test_db` + live temp Ollama)**: **`8 / 8` steps PASS**
- **Advanced Quiz & Flashcards (`test_advanced_quiz_flashcards.py` in `isolated_test_db` + live temp Ollama)**: **`10 / 10` steps PASS**
- **Dev Database Integrity (`backend/documents.db`)**: Verified unchanged (`documents = 102`, `conversations = 102`, `research_paper_analyses = 1`).

---

## 15. Strict Scope Audit

- Did NOT implement Research Paper Analyzer Phase 2 (no critical grading, research gap generation, literature synthesis, contradiction detection, citation networks, or knowledge graphs).
- Did NOT add external research APIs or cloud LLM dependencies.
- Did NOT alter vector stores, SQLite database engine, TrOCR Base, OCR 3.5, or Layout Intelligence logic.
- Kept existing callers of `ollama_client` (`8192` context default) completely unchanged.

---

## 16. Known Remaining Edge Cases

1. **Real Third-Party IEEE Two-Column / ACM PDF Extraction Gaps**: Multi-column PDF text ordering in real-world PyMuPDF extractions without reading-order sorting was **not** tested directly against a native two-column IEEE/ACM PDF in `documents.db` (only synthetic text fixtures).
2. **Cold-Start Local CPU Ollama Latency**: When `llama3.2` weights are completely cold in memory, the first JSON completion on CPU can still approach or exceed `35s`; warm runs complete around `~24.4s` on this CPU.
3. **Unparsed Visual Charts/Tables**: Phase 1 strictly extracts caption/prose references (`visually_parsed: false`) and does not read numeric bars/points rendered solely inside bitmap images.
4. **Global Pre-Existing ESLint Issues**: Repository-wide `npm run lint` fails on pre-existing non-research files (`AIHealthIndicator.jsx` etc.), while all Research Paper UI files pass with `0` errors.

---

## 17. Exact Verification Breakdown: Proven vs Validated vs Synthetic

- **PROVEN BY DIRECT EXECUTION**:
  - `37/37` Research Paper Analyzer unit/API tests (`tests.test_research_paper_analyzer`)
  - `116/116` combined 8-suite backend tests
  - `18/18` Multi-Document Chat, `10/10` Comparison, `10/10` Mind Map, isolated `8`-step Phase 3 Intelligence & `10`-step Advanced Quiz/Flashcards
  - `13/13` frontend Node tests, `0` ESLint errors on research files, Vite build PASS
  - Dev DB (`backend/documents.db`) unchanged (`102 / 102 / 1`)
- **VALIDATED ON AVAILABLE REAL CORPUS (`isolated_test_db(clone_dev_db=True)`)**:
  - `doc #2` (`8p` journal PDF): both `deterministic_fallback` (`494.72 ms`) and live `ollama_hybrid` (`24,861.05 ms`), `23/23` grounded
  - `doc #5` (`160p` thesis PDF): `2,376.09 ms`, `86` sections, `26/26` grounded, `0` ToC leaks (`95.36 ms` cached)
  - `doc #1` resume (`0.02` non-research), `doc #3` DOCX (`0.50` borderline -> manual override honored), `doc #12` handwritten PDF (`0.02` non-research)
- **VALIDATED ON SYNTHETIC FIXTURES / MOCKS**:
  - IEEE two-column (`PacketGuard`), ACM CCS (`VeriSQL`), ToC + structural number traps (`NumGuard`), missing minimal paper (`MeshRoute`), student assignment, enterprise product manual, handwritten note w/ academic keywords, Ollama `35s` timeout & empty JSON mocks (`tests 21-37` and `synthetic_fixtures`).
- **NOT YET VALIDATED**:
  - Live interactive Chrome browser click-through (DevTools MCP / Playwright unavailable in environment)
  - Real downloaded IEEE two-column and ACM SIGMOD/CHI PDF binaries inside PyMuPDF ingestion.

---

## 18. Confidence Score & Rationale

**Readiness Assessment: `9.1 / 10` for Research Paper Analyzer Phase 1 (Textual & Source-Grounded Scope)**

- **Strengths**: Strict `1.0` evidence coverage across all `14` benchmark runs, `0` ToC leaks, `0` structural-number false positives, `0` visual fabrications, `0` wrong evidence routes, successful live CPU `ollama_hybrid` completion (`24.86s`), sub-second deterministic extraction (`0.09s–2.38s` even at `160` pages), and clean regression/tenant isolation.
- **Deductions (`-0.9`)**: `-0.5` because no native two-column IEEE/ACM PDF exists in the local corpus for real PDF column-ordering verification; `-0.4` because Chrome DevTools MCP was unavailable for live headless DOM click-through of Cases 1–6.

---

## 19. Safe Next Phase Entry Criteria (Before Phase 2)

Before starting Research Paper Analyzer Phase 2 (Critical Analysis / Research Gaps / Multi-Paper Synthesis):

1. Ingest 2–3 real native two-column IEEE and ACM PDFs through `documents/upload` and verify PyMuPDF column ordering + ToC/footnote separation end-to-end.
2. Run a quick manual live browser walkthrough of Cases 1–6 in Chrome on `/research-analyzer` (with Vite + FastAPI active) to visually confirm drawer animations and long-thesis scrolling UX.
3. Freeze Phase 1 deterministic + hybrid regression (`tests.test_research_paper_analyzer`) as a permanent CI gate before introducing any Phase 2 synthesis endpoints.

