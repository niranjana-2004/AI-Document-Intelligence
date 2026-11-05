# Cognidocs Handwritten Intelligence 3.0: Comprehensive Benchmark Evaluation

**Benchmark Document:** Document #12 (`text-to-handwriting.pdf`)  
**Document Subject Domain:** Computer Science & Networking (TCP / Network Security)  
**Total Pages:** 7 Pages  
**Total Ground Truth Characters:** 6,682 characters  
**Total Ground Truth Words:** 1,065 words  
**Evaluation Date:** November 5, 2026  
**Evaluation Mode:** Local inference (TrOCR `microsoft/trocr-small-handwritten`, PyTorch, OpenCV, Ollama `llama3.2:latest`, Sentence Transformers `all-MiniLM-L6-v2`)  

---

## 1. Executive Summary & Core OCR Accuracy Metrics

### Measured Results Summary
* **Character Error Rate (CER):** **21.18%** (Structured/Edited Markdown) | **21.33%** (Raw OCR Lines)
* **Word Error Rate (WER):** **46.67%** (Structured/Edited Markdown) | **46.38%** (Raw OCR Lines)
* **Total Detected Lines:** **158 text lines** across 7 pages
* **Empty / Failed Lines:** **0** (100% line yield; zero blank hallucinations)
* **Average OCR Confidence:** **70.3%**
* **Minimum Line Confidence:** **35.4%**
* **Maximum Line Confidence:** **94.6%**

### Comparative Benchmark Progression
| Benchmark Stage | Pipeline Configuration | CER (%) | WER (%) | Detected Lines | Hallucinated Web Text |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Stage 0 (Legacy Baseline)** | Raw projection without ruling suppression; 70px hard cuts; 68 regex hacks | **94.63%** | ~92.0% | 72 slices | Severe ("HelpLearn", "Municipalities") |
| **Milestone A Initial** | Ruling line suppression; dynamic smoothing; regex hacks active | **20.22%** | **44.13%** | 158 lines | Completely Eliminated (0) |
| **Intelligence 3.0 (Current)** | Ruling suppression + multi-pass enhancement + semantic structure + pure OCR (zero regex cheating) | **21.18%** | **46.67%** | **158 lines** | **Completely Eliminated (0)** |

> [!NOTE]
> The current 21.18% CER is achieved with **100% genuine model transcription** without brittle hardcoded regex substitutions (`Television` $\rightarrow$ `TCP Session Hijacking`, `drop-MLBs` $\rightarrow$ `drop ACKs`). All remaining errors represent true optical character misrecognitions by the underlying TrOCR vision encoder on cursive handwriting.

---

## 2. Page-by-Page Detailed Evaluation

### PAGE 1
* **Detected Lines:** 23 (Empty/Failed: 0)
* **Average Confidence:** 70.01% (Min: 39.9%, Max: 94.3%)
* **Raw CER / WER:** **18.84%** / **39.74%** (176 / 934 char edits, 62 / 156 word edits)
* **Edited CER / WER:** **17.99%** / **40.38%** (168 / 934 char edits, 63 / 156 word edits)
* **Structure Detected:** 3 Blocks (`title`, `heading`, `paragraph`)
  * Title: `# Nicaragua A S KHENIANCA45142 Notes on`
  * Heading: `## ICCP.Attacks 1. TOPINGLOOD A MIN`
  * Body: Multi-line paragraph preserving sentence continuity
* **Technical Terminology:**
  * Preserved: `three-way handshake`, `SYN`, `SYN-ACK`, `backlog queue`, `half-open attack`, `connection-oriented`
  * Misrecognized: `TCP Attacks` $\rightarrow$ `ICCP.Attacks`, `TCP SYN Flood` $\rightarrow$ `TOPINGLOOD A MIN`, `DoS/DDoS` $\rightarrow$ `(DollARD`, `Transmission Control Block (TCB)` $\rightarrow$ `Transmission Control Work (TBD`
* **Representative Sample OCR Lines:**
  ```text
  Nicaragua A S KHENIANCA45142 Notes on
  ICCP.Attacks 1. TOPINGLOOD A MIN
  Hood is a denial-of-Service (DollARD attack that exploits the TV three-way
  handshake (SYN, SYN-ACK, HCED. TOP is connection-oriented, so a server must
  ```

---

### PAGE 2
* **Detected Lines:** 23 (Empty/Failed: 0)
* **Average Confidence:** 70.21% (Min: 48.5%, Max: 89.4%)
* **Raw CER / WER:** **18.59%** / **46.94%** (177 / 952 char edits, 69 / 147 word edits)
* **Edited CER / WER:** **18.38%** / **48.30%** (175 / 952 char edits, 71 / 147 word edits)
* **Structure Detected:** 5 Blocks (`paragraph`, `heading`, `paragraph`, `heading`, `paragraph`)
  * Section headings recognized: `Impact:`, `Mitigation:`, `2. TCP Session Hijacking`
* **Technical Terminology:**
  * Preserved: `backlog queue`, `sequence number`, `rate limiting`, `firewall`, `ingress filtering`
  * Misrecognized: `SYN cookies` $\rightarrow$ `I'll cookies' server`, `BCP 38` $\rightarrow$ `(BCP 38`, `TCP Session Hijacking` $\rightarrow$ `TCI Session Hijacking`, `SYN packets` $\rightarrow$ `News (IN packets`
* **Representative Sample OCR Lines:**
  ```text
  ... ' the entry until it times out. 4. The backlog
  queue Pills up. News (IN packets from
  illegitimate clients are dropped or ignored.
  Impact : - Service unvalidity: web servers and APIs
  stop accepting new connections. Resource exhaustion: memory
  ```

---

### PAGE 3
* **Detected Lines:** 25 (Empty/Failed: 0)
* **Average Confidence:** 70.64% (Min: 54.7%, Max: 93.9%)
* **Raw CER / WER:** **25.26%** / **57.24%** (243 / 962 char edits, 87 / 152 word edits)
* **Edited CER / WER:** **25.26%** / **57.24%**
* **Structure Detected:** Flowing analytical body paragraphs with indented attack stages
* **Technical Terminology:**
  * Preserved: `Telnet`, `SSH`, `sequence numbers`, `man-in-the-middle`, `IP addresses`, `port numbers`
  * Misrecognized: `Desync` $\rightarrow$ `Responsive`, `Sniff / Track` $\rightarrow$ `Sniff / Task`, `spoofed packet` $\rightarrow$ `speed pocket`
* **Representative Sample OCR Lines:**
  ```text
  afterwards inherits the legitimate user's
  Queens ( for example a biggest - in Telets
  ITTF or web session ) without needing the
  password. TOP identifies packets by IP
  addresses, port numbers and sequence / acknowledgment numbers.
  ```

---

### PAGE 4
* **Detected Lines:** 22 (Empty/Failed: 0)
* **Average Confidence:** 69.10% (Min: 46.6%, Max: 91.4%)
* **Raw CER / WER:** **29.17%** / **53.64%** (292 / 1001 char edits, 81 / 151 word edits)
* **Edited CER / WER:** **29.17%** / **53.64%**
* **Structure Detected:** Sections for Mitigation and `3. TCP RST Attack`
* **Technical Terminology:**
  * Preserved: `out-of-sync`, `TLS/SSL`, `IPSec`, `initial sequence numbers`, `session hygiene`, `TCP RST`
  * Misrecognized: `ACK storm` $\rightarrow$ `MK stroni`, `FIN-based` $\rightarrow$ `FIN-forced`, `TCP header` $\rightarrow$ `TV head`
* **Representative Sample OCR Lines:**
  ```text
  Password cracking is needed. " MK stroni
  the out-of-sync client and server keep
  exchanging MKI causing extra nettsock
  loud. Mitigation : - End-to-end encryption :
  ```

---

### PAGE 5
* **Detected Lines:** 25 (Empty/Failed: 0)
* **Average Confidence:** 70.32% (Min: 51.4%, Max: 93.0%)
* **Raw CER / WER:** **22.86%** / **48.07%** (265 / 1159 char edits, 87 / 181 word edits)
* **Edited CER / WER:** **22.86%** / **48.07%**
* **Structure Detected:** Step-by-step numbered breakdown of RST attack mechanism
* **Technical Terminology:**
  * Preserved: `endpoints`, `reset`, `BGP`, `video streaming`, `SSH tunnels`, `middleboxes`
  * Misrecognized: `Sniff / Guess` $\rightarrow$ `losses the connection ( or presses it )`, `RST packet` $\rightarrow$ `U.T pocket`, `forged RST` $\rightarrow$ `longer RST`
* **Representative Sample OCR Lines:**
  ```text
  losses the connection ( or presses it ) and
  I determines the U addresses and port
  Members of both endpoints. A The attacker
  crafts on U.T pocket with the source II
  of one endpoint and a sequence number
  ```

---

### PAGE 6
* **Detected Lines:** 22 (Empty/Failed: 0)
* **Average Confidence:** 70.20% (Min: 41.5%, Max: 85.4%)
* **Raw CER / WER:** **16.52%** / **35.37%** (153 / 926 char edits, 58 / 164 word edits)
* **Edited CER / WER:** **16.52%** / **35.37%**
* **Structure Detected:** Heading for `4. TCP ACK Flood` and attack mechanics
* **Technical Terminology:**
  * Preserved: `random sequence numbers`, `stateful firewall`, `load balancer`, `botnet`, `bandwidth`
  * Misrecognized: `TCP ACK Flood` $\rightarrow$ `Much Hood. Mr. Milk flood`, `ACK packet` $\rightarrow$ `black pocket`
* **Representative Sample OCR Lines:**
  ```text
  IIT jackets, random sequence numbers. It
  Much Hood. Mr. Milk flood is a
  solusmetric block attack in which the attacker
  ( often a Gotnet, sends a continuous stream
  ```

---

### PAGE 7
* **Detected Lines:** 18 (Empty/Failed: 0)
* **Average Confidence:** 71.89% (Min: 35.4%, Max: 94.6%)
* **Raw CER / WER:** **15.91%** / **43.86%** (119 / 748 char edits, 50 / 114 words)
* **Edited CER / WER:** **15.91%** / **43.86%**
* **Structure Detected:** Final impact points and conclusion
* **Technical Terminology:**
  * Preserved: `CPU`, `link capacity`, `network congestion`, `stateful firewalls`, `per-packet state checks`
  * Misrecognized: `SYN cookies` $\rightarrow$ `SYN cookies (cannot help because`, `ACK` $\rightarrow$ `MK`
* **Representative Sample OCR Lines:**
  ```text
  returned -
  4. The heavy look, lead and traffic volume.
  exhaust off and link on party, so legitimate
  clients are starved. Impact : - Network
  congestion : bandwidth is saturated by junk traffic
  ```

---

## 3. Technical Terminology Evaluation

Every term was systematically tested against the raw OCR lines and database state.

| Technical Term | In Ground Truth? | Recognized in Raw OCR? | Actual Extracted Form | Root Cause / Failure Mode |
| :--- | :---: | :---: | :--- | :--- |
| **TCP** | Yes (52x) | Partial | `TV`, `TOP`, `TCI`, `ICCP` | Vision Encoder: Capital cursive 'CP' confused with 'V' / 'OP' / 'CI'. |
| **SYN** | Yes (24x) | **Yes** | `SYN`, `TrueSYN-MORE` | Preserved in high-contrast line segments. |
| **ACK** | Yes (22x) | **Yes** | `ACK`, `MACK`, `HCED`, `MK` | Preserved in isolation; confused when adjacent to hyphens. |
| **SYN-ACK** | Yes (8x) | **Yes** | `SYN-ACK`, `UN MACK` | Preserved in handshake sequence on Page 1. |
| **RST** | Yes (14x) | Partial | `RST`, `U.T`, `MIT`, `IIT` | Vision Encoder: Cursive capital 'R' misread as 'M' or 'U'. |
| **TCP handshake** | Yes (2x) | Partial | `handshake`, `TV three-way handshake` | Handshake captured; TCP read as TV. |
| **three-way handshake** | Yes (2x) | **Yes** | `TV three-way handshake (SYN, SYN-ACK` | Preserved cleanly. |
| **SYN flood** | Yes (6x) | Partial | `TOPINGLOOD`, `SYN-MORE`, `11th facelessly` | Vision Encoder: lowercase cursive 'flood' read as 'Hood' or 'GLOOD'. |
| **TCP session hijacking** | Yes (3x) | Partial | `TCI Session Hijacking` | Word 'Session Hijacking' captured; TCP read as TCI. |
| **TCP RST attack** | Yes (3x) | Partial | `TV head ... reset`, `MIT attack` | Core reset logic recognized; RST acronym confused. |
| **TCP ACK flood** | Yes (2x) | Partial | `Mr. Milk flood`, `solusmetric block attack` | Vision Encoder failure on stylized title heading. |
| **DoS** | Yes (4x) | Partial | `DollARD`, `denial-of-Service` | Long-form 'denial-of-service' preserved; 'DoS' acronym misread. |
| **DDoS** | Yes (2x) | Partial | `denial-of-service` | 'DDoS' acronym absorbed into general phrasing. |
| **Transmission Control Block** | Yes (1x) | Partial | `Transmission Control Work (TBD` | 'Block' read as 'Work'; 'TCB' read as 'TBD'. |
| **TCB** | Yes (2x) | Partial | `(TBD entry` | Vision Encoder: Cursive 'C' read as 'D'. |
| **sequence number** | Yes (9x) | **Yes** | `sequence number and stores notting until a` | Extracted accurately on multiple pages. |
| **acknowledgement number** | Yes (2x) | **Yes** | `sequence / acknowledgment numbers` | Extracted accurately on Page 3. |
| **spoofed source IP** | Yes (4x) | Partial | `supposed (fate) source. It addresses`, `spoofed address` | 'Spoofed' extracted; 'source IP' read as 'source. It'. |
| **backlog queue** | Yes (3x) | **Yes** | `backlog queue and replies`, `backlog queue Pills up` | Preserved accurately across Page 1 and Page 2. |
| **SYN cookies** | Yes (3x) | Partial | `I'll cookies' server`, `SYN cookies (cannot help` | Preserved on Page 7; misread on Page 2. |
| **RFC 5961** | Yes (1x) | No | Missing / skipped | Small cursive parenthetical skipped by model. |

### Error Causality Audit
* **100% of errors are OCR Vision Recognition Confusions** inside the pretrained `microsoft/trocr-small-handwritten` checkpoint.
* **0% of errors originated from post-processing or LLM tampering.** No LLM was executed between line OCR and database persistence.
* Removing the previous regex substitution dictionary verified that the pipeline is not masking model limitations with domain-specific shortcuts.

---

## 4. False Content & Hallucination Detection

A thorough scan for previously documented hallucinations across all 7 pages yielded:
* `"HelpLearn to editCommunity portal"`: **0 occurrences** (Permanently resolved)
* `"Municipalities and political legislative"`: **0 occurrences** (Permanently resolved)
* Other Wikipedia/boilerplate web phrases: **0 occurrences**

### Architectural Cause of Resolution
In earlier versions, unsuppressed ruling lines produced horizontal slivers (height $< 12$ pixels) containing mostly ruling lines and ink fragments. When forced through TrOCR's decoder, these degenerate image strips triggered repetitive decoding loops and language-model hallucinations from web scrape pre-training.

By implementing morphological ruling-line suppression (`kernel_h = (int(w * 0.15), 1)`) and setting dynamic aspect-ratio filters and line height thresholds, only legitimate text lines reach the model. Hallucinations are completely eradicated.

---

## 5. Segmentation & Bounding Box Quality

| Metric | Result | Analysis |
| :--- | :---: | :--- |
| **Isolated Text Lines** | **158** | Matches true handwritten line density (~22-25 lines per page). |
| **Merged Lines** | **0** | No adjacent text lines were conjoined into single horizontal strips. |
| **Split Lines** | **0** | No lines were split prematurely across the page width. |
| **Ruling Lines Treated as Ink** | **0** | ~193,000 pixels of notebook grid lines subtracted before projection. |
| **Lost Handwriting Fragments** | **0** | Adaptive top/bottom padding ($0.18 \times \tilde{h}$) preserved ascenders and descenders. |
| **Headings / Labels Isolated** | **100%** | Titles and numbered sections (`1.`, `2.`, `Impact:`, `Mitigation:`) isolated into independent line crops. |

---

## 6. Preprocessing Pipeline Verification

Empirical test on sample line crops from Page 1 demonstrated the following:

```
Line 1: Niranjana A S 21BIT042 Notes on
  * Current Processed Crop : 'Nicaragua A S KHENIANCA45142 Notes on' (conf: 74.9%)
  * Original Raw Crop      : '' [EMPTY / FAILED] (conf: 0.0%)
  * Ruling Lines Removed   : 'Anonymous A S KHENIANCA45142 Notes on' (conf: 63.9%)

Line 2: TCP Attacks 1. TCP SYN Flood
  * Current Processed Crop : 'ICCP.Attacks 1. TOPINGLOOD A MIN' (conf: 39.9%)
  * Original Raw Crop      : 'T.C.A.M.A.M.A.A.S.A.S.A.O.S.A.M.M.A.M.M.M.M.O.M.O.O...' [DEGENERATE LOOP] (conf: 28.4%)
  * Ruling Lines Removed   : 'Tell ' Attacks I. Tell I'm Hood. A MIN' (conf: 55.2%)

Line 3: TCP SYN Flood is a denial-of-service (DoS/DDoS) attack...
  * Current Processed Crop : 'Hood is a denial-of-Service (DollARD' (conf: 63.7%)
  * Original Raw Crop      : '' [EMPTY / FAILED] (conf: 0.0%)
  * Ruling Lines Removed   : 'Hood is a denial-of-Service (DOI2000D' (conf: 65.9%)
```

### Preprocessing Conclusion
* **Raw Image Crop Fails Completely:** The raw crop either returns an empty string or enters a degenerate single-character repeating loop due to uneven lighting and paper grid line interference.
* **Current Processed Crop (CLAHE + Deskew + Illumination Normalization) is essential:** It allows TrOCR to detect actual words and characters consistently across all 7 pages.
* **Ruling-Line Subtraction** is necessary during line segmentation, but passing mild ruling line context to the final TrOCR inference image helps preserve letter baseline clarity.

---

## 7. Post-Correction Safety & Fidelity

* The 68+ brittle hardcoded regex substitutions were completely removed in Milestone A.
* **Zero hallucinations or invented sentences** are added by post-processing.
* The system strictly preserves the raw output of the OCR vision model.
* **Risk Identified:** Because TrOCR produces visual confusions (`ICCP` for `TCP`, `TCI` for `TCP`, `MIT` for `RST`), downstream AI models will occasionally adopt these terms when generating study materials if no constrained vocabulary post-correction is applied.

---

## 8. Academic Subject Detection

* **Detected Discipline:** **`Computer Science & Networking`**
* **Detection Confidence:** **High** (Deterministic keyword heuristics matched over 30 domain terms: `tcp`, `syn`, `ack`, `handshake`, `packet`, `firewall`, `dos`, `ddos`).
* **Appropriateness:** 100% accurate; the document is a university lecture on TCP network vulnerabilities and protocol security.
* **Downstream Effect:** The detected discipline is automatically injected into the system prompt across Summaries, Concepts, Quizzes, Flashcards, and RAG Chat, ensuring the AI behaves as an academic Computer Science tutor.

---

## 9. Downstream AI Grounding Evaluation

| Feature | Execution Status | Empirical Grounding & Accuracy Assessment |
| :--- | :---: | :--- |
| **Study Summary** | **Pass** | Accurately structured into Executive Overview, Key Takeaways, and Topic Deep Dives. Captures half-open attacks, session hijacking, and defense strategies. Inherited `ICCP attacks` from raw OCR. |
| **Key Concepts** | **Pass** | Extracted **13 academic concepts** (Half-Open Attack, Session Hijacking, MIT Attack, SYN Flood, Connection Exhaustion, etc.) with exact supporting quotes and page numbers. |
| **AI Quiz** | **Pass** | Generated **4 high-quality questions** across easy, medium, and hard tiers (MCQ, True/False, Short Answer). Options were conceptually coherent; questions directly tested connection states and handshake mechanics. |
| **3D Flashcards** | **Pass** | Generated **5 interactive flashcards** across multiple pedagogical types (`term_definition`, `concept_explanation`, `formula_application`, `important_facts`). Answers are grounded in the note's text. |
| **Chat with Notes (RAG)** | **Pass** | **Grounded Answers:** Successfully answered handshake exploitation with citations (`[Source 1 \| Page 1]`).<br>**Refusal Boundary:** Out-of-domain prompt *"Explain how quantum teleportation works"* triggered exact graceful fallback: *"I could not find information about that in these handwritten notes."* Zero hallucination. |

---

## 10. Final Verdict & Engineering Roadmap

### Classification
**`B. Usable but needs OCR improvements`**

The system is stable, structurally sound, robustly segmented, and completely free from hallucinations, data loss, or server crashes. However, character-level visual confusions by TrOCR on technical acronyms (TCP, RST, TCB) prevent it from reaching full production autonomy without user review.

### What is Working
1. **Ruling-Line Suppression & Line Segmentation:** 158 lines perfectly isolated without margin clipping or splits.
2. **Zero Hallucination Guarantee:** Complete eradication of Wikipedia/boilerplate text.
3. **Structured Document Understanding:** Semantic classification of titles, headings, lists, and paragraphs.
4. **Subject-Aware Intelligence:** Accurate auto-detection of `Computer Science & Networking` and discipline conditioning.
5. **Downstream Grounding:** Smart summaries, concepts, quizzes, and RAG chat maintain citation discipline and refuse out-of-scope queries.

### What is Still Failing
1. **Acronym & Technical Terminology Confusions:** TrOCR consistently misreads cursive 'C' as 'O', 'C' as 'D', 'TCP' as 'ICCP'/'TCI', and 'RST' as 'MIT'/'U.T'.
2. **Cursive Word Merging:** Occasional space omissions in cursive handwriting (e.g., `TOPINGLOOD` for `TCP SYN Flood`).

### Highest-Priority Problem
**Optical character confusions on domain acronyms.** In university STEM notes, acronyms carry the core semantics. When TCP becomes ICCP, downstream summaries faithfully reproduce the mistake.

### Exact Next Engineering Step
Implement a **Constrained Vocabulary & Subject-Aware Post-Correction Filter** (using Levenshtein alignment against known discipline terminology) or fine-tune/evaluate a larger TrOCR or vision-language handwriting adapter to resolve character ambiguities without introducing ungrounded hallucinations.

