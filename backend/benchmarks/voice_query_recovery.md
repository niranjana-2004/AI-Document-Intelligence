# Cognidocs Phase 2 — Controlled Voice Query Recovery Benchmark

## Summary Metrics

- **Total benchmark queries**: `40` (`5` clean, `29` distorted/technical, `6` ambiguous/ordinary/out-of-scope)
- **Recovery accuracy (`correct / attempted`)**: `29/29` (**100.0%**)
- **Distorted recovery recall**: **100.0%**
- **False recovery rate**: `0/11` (**0.0%**)
- **Abstention accuracy**: `6/6` (**100.0%**)

## Retrieval Impact on Distorted Queries (Raw STT vs. Recovered Query)

- **Confidence gate (`>= 0.40`) pass rate**: `12/29` -> **`27/29`**
- **Expected source + term hit rate**: `18/29` -> **`29/29`**
- **Average top retrieval score**: `0.3193` -> **`0.634`**
- **Average top MiniLM similarity**: `0.2896` -> **`0.5215`**

## Latency

- **Average warm recovery overhead**: **34.64 ms** (p95: **132.17 ms**, max: **147.5 ms**)
- **Average cold recovery overhead (incl. doc vocab extraction)**: **88.13 ms**

## Per-Case Results

| ID | Domain | Raw Transcript | Recovered Query | Decision | Raw Score | Recovered Score | Warm ms | Pass |
|---|---|---|---|---|---:|---:|---:|---|
| `tcp_clean_01` | Computer Networks (Handwritten) | `What is a SYN flood?` | `What is a SYN flood?` | `UNCHANGED` (1.00) | 0.653 | 0.653 | 48.7 | PASS |
| `tcp_clean_02` | Computer Networks (Handwritten) | `What is TCP?` | `What is TCP?` | `UNCHANGED` (1.00) | 0.595 | 0.595 | 46.9 | PASS |
| `tcp_distorted_01_swion` | Computer Networks (Handwritten) | `What is a swion flood?` | `What is a SYN flood?` | `RECOVERED` (0.93) | 0.368 | 0.653 | 59.4 | PASS |
| `tcp_hyphen_01_synflood` | Computer Networks (Handwritten) | `What is S-Y-N-Flood?` | `What is SYN flood?` | `RECOVERED` (0.95) | 0.480 | 0.663 | 50.8 | PASS |
| `tcp_spaced_01_syn` | Computer Networks (Handwritten) | `What is S Y N?` | `What is SYN?` | `RECOVERED` (0.92) | 0.323 | 0.575 | 46.9 | PASS |
| `tcp_spaced_02_syn_flood` | Computer Networks (Handwritten) | `What is a S Y N flood?` | `What is a SYN flood?` | `RECOVERED` (0.98) | 0.467 | 0.653 | 46.1 | PASS |
| `tcp_coloc_01_sin_flood` | Computer Networks (Handwritten) | `What is a sin flood?` | `What is a SYN flood?` | `RECOVERED` (0.81) | 0.311 | 0.653 | 46.0 | PASS |
| `tcp_spaced_03_tcp` | Computer Networks (Handwritten) | `What is T C P?` | `What is TCP?` | `RECOVERED` (0.92) | 0.294 | 0.595 | 46.9 | PASS |
| `tcp_spaced_04_tcb` | Computer Networks (Handwritten) | `What is a T C B?` | `What is a TCB?` | `RECOVERED` (0.92) | 0.262 | 0.519 | 46.6 | PASS |
| `tcp_spaced_05_hijacking` | Computer Networks (Handwritten) | `What is T C P session hijacking?` | `What is TCP session hijacking?` | `RECOVERED` (0.98) | 0.526 | 0.713 | 48.7 | PASS |
| `tcp_number_01_rfc5961` | Computer Networks (Handwritten) | `What is R F C five nine six one?` | `What is RFC 5961?` | `RECOVERED` (0.94) | 0.000 | 0.517 | 47.8 | PASS |
| `tcp_supp_01_rst` | Computer Networks (Printed) | `What is a TCP rest attack?` | `What is a TCP RST attack?` | `RECOVERED` (0.82) | 0.540 | 0.743 | 10.6 | PASS |
| `tcp_supp_02_ack_flood` | Computer Networks (Printed) | `What is a T C P A C K flood?` | `What is a TCP ACK flood?` | `RECOVERED` (0.98) | 0.381 | 0.782 | 5.0 | PASS |
| `tcp_supp_03_ddos` | Computer Networks (Printed) | `What is D D O S?` | `What is DDoS?` | `RECOVERED` (0.92) | 0.000 | 0.651 | 4.3 | PASS |
| `tcp_supp_04_syn_cookies` | Computer Networks (Printed) | `What are syn cookies?` | `What are SYN cookies?` | `RECOVERED` (0.97) | 0.684 | 0.684 | 4.6 | PASS |
| `abst_ambiguous_01_sin` | Computer Networks (Handwritten) | `What is sin?` | `What is sin?` | `SUGGESTED` (0.56) | 0.000 | 0.000 | 46.8 | PASS |
| `abst_ordinary_01_prose_sin` | Computer Networks (Handwritten) | `Tell me about sin and forgiveness` | `Tell me about sin and forgiveness` | `UNCHANGED` (1.00) | 0.000 | 0.000 | 58.6 | PASS |
| `abst_ordinary_02_rest` | Computer Networks (Printed) | `I need to rest before studying attacks` | `I need to rest before studying attacks` | `UNCHANGED` (1.00) | 0.000 | 0.000 | 7.0 | PASS |
| `abst_ordinary_03_five_examples` | Computer Networks (Handwritten) | `Give me five examples of TCP attacks` | `Give me five examples of TCP attacks` | `UNCHANGED` (1.00) | 0.482 | 0.482 | 49.4 | PASS |
| `abst_crossdoc_01_wrong_doc` | Web Development (Handwritten) | `What is a swion flood?` | `What is a swion flood?` | `UNCHANGED` (1.00) | 0.000 | 0.000 | 20.5 | PASS |
| `web_spaced_01_css` | Web Development (Handwritten) | `What is C S S?` | `What is CSS?` | `RECOVERED` (0.94) | 0.275 | 0.668 | 11.0 | PASS |
| `web_spaced_02_html` | Web Development (Handwritten) | `How does H T M L differ from css?` | `How does HTML differ from CSS?` | `RECOVERED` (0.90) | 0.444 | 0.535 | 13.0 | PASS |
| `web_clean_01` | Web Development (Handwritten) | `What is CSS used for?` | `What is CSS used for?` | `UNCHANGED` (1.00) | 0.657 | 0.657 | 13.3 | PASS |
| `llm_spaced_01_trocr` | AI & LLM (Printed) | `What is T r O C R?` | `What is TrOCR?` | `RECOVERED` (0.92) | 0.000 | 0.563 | 6.1 | PASS |
| `llm_spaced_02_cer_wer` | AI & LLM (Printed) | `Explain C E R and W E R` | `Explain CER and WER` | `RECOVERED` (0.95) | 0.000 | 0.400 | 5.3 | PASS |
| `llm_clean_01` | AI & LLM (Printed) | `How does TrOCR extract handwritten text?` | `How does TrOCR extract handwritten text?` | `UNCHANGED` (1.00) | 0.684 | 0.684 | 28.5 | PASS |
| `cloud_split_01_cephvault` | Cloud Storage & KMS (Printed) | `What is sef vault?` | `What is CephVault?` | `RECOVERED` (0.89) | 0.501 | 0.808 | 147.5 | PASS |
| `cloud_spaced_01_kms` | Cloud Storage & KMS (Printed) | `What is K M S in Ceph?` | `What is KMS in Ceph?` | `RECOVERED` (0.92) | 0.629 | 0.703 | 54.7 | PASS |
| `cloud_spaced_02_kek_dek` | Cloud Storage & KMS (Printed) | `Compare K E K and D E K` | `Compare KEK and DEK` | `RECOVERED` (0.95) | 0.367 | 0.611 | 17.4 | PASS |
| `cloud_clean_01` | Cloud Storage & KMS (Printed) | `What is CephVault?` | `What is CephVault?` | `UNCHANGED` (1.00) | 0.808 | 0.808 | 11.5 | PASS |
| `cloud_enc_distorted_01` | Cloud Security (Printed) | `What is homomorfic encryption?` | `What is homomorphic encryption?` | `RECOVERED` (0.93) | 0.563 | 0.846 | 132.2 | PASS |
| `phys_spaced_01_emf` | Physics (Printed) | `What is E M F in Faraday's law?` | `What is EMF in Faraday's law?` | `RECOVERED` (0.92) | 0.572 | 0.759 | 4.8 | PASS |
| `phys_term_01_schrodinger` | Physics (Printed) | `Explain the Shrodinger equation` | `Explain the Schrodinger equation` | `RECOVERED` (0.80) | 0.464 | 0.683 | 9.3 | PASS |
| `phys_spaced_02_led` | Physics (Printed) | `How does an L E D emit photons?` | `How does an LED emit photons?` | `RECOVERED` (0.89) | 0.492 | 0.683 | 11.9 | PASS |
| `math_spaced_01_ode` | Mathematics (Printed) | `What is an O D E?` | `What is an ODE?` | `RECOVERED` (0.92) | 0.000 | 0.608 | 4.5 | PASS |
| `math_spaced_02_svd` | Mathematics (Printed) | `How is S V D computed?` | `How is SVD computed?` | `RECOVERED` (0.84) | 0.000 | 0.633 | 4.2 | PASS |
| `math_term_01_eigenvector` | Mathematics (Printed) | `What is an eiganvector?` | `What is an eigenvector?` | `RECOVERED` (0.80) | 0.000 | 0.684 | 11.5 | PASS |
| `math_ordinary_01_trig_sin` | Mathematics (Printed) | `What is sin in trigonometry?` | `What is sin in trigonometry?` | `UNCHANGED` (1.00) | 0.578 | 0.578 | 4.1 | PASS |
| `multidoc_01_net_web` | Multi-Doc (Handwritten Net + Web) | `Compare swion flood and C S S` | `Compare SYN flood and CSS` | `RECOVERED` (0.84) | 0.317 | 0.414 | 92.2 | PASS |
| `multidoc_02_net_llm` | Multi-Doc (Printed LLM + Handwritten Net) | `Explain T r O C R and T C P` | `Explain TrOCR and TCP` | `RECOVERED` (0.92) | 0.000 | 0.389 | 60.8 | PASS |
