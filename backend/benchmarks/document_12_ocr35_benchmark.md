# Cognidocs OCR 3.5 — Context-Aware Word & Phrase Recovery Benchmark Report

**Document**: Document #12 (`text-to-handwriting.pdf`, Computer Networks Lecture Notes)  
**Evaluation Date**: 2026-11-08 11:07:24  
**Model**: `microsoft/trocr-small-handwritten` (100% Local CPU Inference)  
**Pipeline**: Cognidocs Handwritten Intelligence 3.5 (Boundary Analysis + Context Ranking + Phrase Recovery + Safety Gate)  
**Benchmark Execution Time**: 81.61 seconds (11.66s per page)  

---

## 1. Executive Summary & Progression

Cognidocs OCR 3.5 introduces:
1. **Adaptive Line-Scale & Word Boundary Analysis**: Visual column whitespace projection dips and inter-word gap metrics dynamically scaled to line height and character width.
2. **Phrase and Multi-Token Compound Recovery**: Merging erroneously split compound words (`hand` + `shake` $\rightarrow$ `handshake`, `back` + `log` $\rightarrow$ `backlog`, `look` + `up` $\rightarrow$ `lookup`) and hyphenated compounds (`three` + `way` $\rightarrow$ `three-way`, `half` + `open` $\rightarrow$ `half-open`, `per` + `packet` $\rightarrow$ `per-packet`, `denial` + `of` + `service` $\rightarrow$ `denial-of-service`).
3. **Cross-Page Document Consistency Index**: Tracking word frequencies and bigrams across the entire multi-page document to corroborate weak tokens using high-frequency occurrences.
4. **Context-Aware Character Disambiguation**: Exploring cursive stroke confusion graphs with 3-word and 5-word local context colocation scoring.
5. **Multi-Signal Candidate Ranking & Safety Gate**: Enforcing the hierarchy of trust (Image > OCR Model > Visual Stroke > Document Consistency > Context > Plausibility) with common-word protection guardrails (valid common words like `the`, `is`, `server` are protected from arbitrary mutation).
6. **Student Manual Edit & Raw Transcription Preservation**: Original OCR output (`raw_transcription`) and manual user adjustments are permanently preserved.

### Progression Across Milestones (Document #12)

| Pipeline Version | Primary Model | CER | WER | Word Accuracy | Technical Term F1 | Hallucination / Web Leakage | False Correction Rate |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline (Pre-3.0)** | Tesseract/TrOCR | 94.63% | >95% | <5.0% | 0.00 | Severe Wikipedia Hallucinations | High |
| **OCR 3.0 (Intelligence)** | TrOCR Small | 20.22% | 44.13% | 55.87% | 0.40 | 0% | Moderate |
| **OCR 3.1 (Technical Recovery)**| TrOCR Small | 21.18% | 46.67% | 53.33% | 0.67 | 0% | Low |
| **OCR 3.2 (Visual Recovery)** | TrOCR Small | 17.55% | 39.46% | 60.54% | 0.82 | 0% | <2.0% |
| **OCR 3.3 (General Accuracy)** | TrOCR Small | 17.16% | 38.64% | 61.36% | 0.88 | 0% | 1.1% |
| **OCR 3.4 (Base Evaluation)** | TrOCR Base | 16.59% | 39.06% | 60.94% | 0.82 | Leading `#`, quotes, `...` | 4.8% (13.3x slower) |
| **OCR 3.5 (Context-Aware)** | **TrOCR Small** | **21.31%** | **44.79%** | **55.21%** | **0.85 (84.6%)** | **0% (Zero)** | **8.11%** |

---

## 2. Page-by-Page OCR 3.5 Results

| Page # | Lines | Tokens | OCR Conf | Raw CER | Recovered CER | Raw WER | Recovered WER | Word Acc | Accepted Corrs | Suggested Corrs |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Page 1** | 23 | 158 | 70.0% | 18.84% | **15.95%** | 39.74% | **32.69%** | **67.31%** | 14 | 3 |
| **Page 2** | 23 | 157 | 70.2% | 18.59% | **18.38%** | 46.94% | **46.94%** | **53.06%** | 7 | 4 |
| **Page 3** | 25 | 167 | 71.2% | 23.80% | **23.70%** | 50.00% | **49.34%** | **50.66%** | 1 | 1 |
| **Page 4** | 22 | 149 | 69.8% | 29.57% | **29.67%** | 52.32% | **52.32%** | **47.68%** | 3 | 1 |
| **Page 5** | 25 | 170 | 68.0% | 23.55% | **23.38%** | 50.83% | **50.28%** | **49.72%** | 2 | 3 |
| **Page 6** | 22 | 166 | 69.4% | 18.36% | **17.60%** | 37.80% | **35.37%** | **64.63%** | 8 | 4 |
| **Page 7** | 18 | 119 | 70.5% | 19.12% | **18.85%** | 50.00% | **47.37%** | **52.63%** | 2 | 0 |
| **Overall** | **158** | **1086** | **69.9%** | **21.91%** | **21.31%** | **46.67%** | **44.79%** | **55.21%** | **37** | **16** |

---

## 3. Technical Terminology Recovery Performance

| Term | Raw OCR State | OCR 3.5 State | Status |
| :--- | :--- | :--- | :--- |
| `TCP` | Missed | **Found** | `RECOVERED` |
| `SYN` | Found | **Found** | `PRESERVED` |
| `ACK` | Found | **Found** | `PRESERVED` |
| `RST` | Missed | **Missed** | `MISSED` |
| `TCB` | Missed | **Found** | `RECOVERED` |
| `DoS` | Missed | **Found** | `RECOVERED` |
| `DDoS` | Missed | **Missed** | `MISSED` |
| `SYN flood` | Missed | **Found** | `RECOVERED` |
| `TCP session hijacking` | Missed | **Found** | `RECOVERED` |
| `TCP RST attack` | Missed | **Missed** | `MISSED` |
| `TCP ACK flood` | Missed | **Missed** | `MISSED` |
| `Transmission Control Block` | Missed | **Found** | `RECOVERED` |
| `backlog queue` | Found | **Found** | `PRESERVED` |
| `SYN cookies` | Missed | **Found** | `RECOVERED` |
| `RFC 5961` | Missed | **Found** | `RECOVERED` |

- **Raw Technical Terms Detected**: 3 / 15 (20.0%)
- **Recovered Technical Terms Detected**: 11 / 15 (73.3%)
- **Precision**: 100.0%
- **Recall**: 73.3%
- **F1 Score**: 84.6%

---

## 4. Recovery Signal & Correction Breakdown

- **Total Tokens Analyzed**: 1086
- **Suspicious Tokens Flagged**: 433
- **Compound Phrase Merges (`handshake`, `backlog`, `lookup`)**: 2
- **Hyphenated Compounds (`three-way`, `half-open`, `per-packet`)**: 1
- **Word Boundary Splits (Ink-Valley Grounded)**: 1
- **Parenthetical Text Recovered (`(DoS)`, `(TCB)`)**: 4
- **Character Confusions Disambiguated**: 6
- **Punctuation & Delimiters Restored**: 6
- **Total Auditable Corrections**: 53
- **Accepted Corrections**: 37
- **Suggested Corrections**: 16
- **Rejected Candidates**: 0
- **False Corrections**: 3 (False Correction Rate: 8.11%)

---

## 5. False Correction Audit & Safety Verification

False corrections detected across all 7 pages: 3

| Page | Original Token | Suggested Replacement | Recovery Type |
| :---: | :--- | :--- | :--- |
| Page 1 | `ever` | `even` | `character` |
| Page 4 | `(blind` | `(blind)` | `punctuation` |
| Page 6 | `(often` | `(often)` | `punctuation` |

---

## 6. Architecture & Safety Guarantees

1. **Hierarchy of Trust Strictly Enforced**:
   - Handwritten image evidence (active ink columns, whitespace valleys) takes precedence over all statistical priors.
   - Any candidate alternative with visual similarity $< 0.55$ is unconditionally REJECTED.
   - High-confidence common English words are protected by an elevated acceptance gate ($\ge 0.85$ composite score + $\ge 3$ independent corroborations).
2. **Deterministic & CPU-Compatible**:
   - The entire OCR 3.5 pipeline runs on local CPU in 81.61s across all 7 pages (~11.66s per page).
   - Zero cloud AI APIs, zero external network dependencies, zero privacy leaks.
3. **Auditability & Student Control**:
   - Every token retains its bounding box, candidate alternatives, and multi-signal score vector (`visual_score`, `boundary_confidence`, `context_score`, `language_score`, `technical_score`, `document_consensus`, `final_score`).
   - Original OCR raw text and manual user adjustments are permanently preserved in the database.
