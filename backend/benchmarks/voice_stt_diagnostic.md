# Cognidocs Voice STT Diagnostic Report (Phase 2.1)

- **Capture Mode**: `real_browser_microphone`
- **Whisper Model**: `base.en` (`int8`, CPU)
- **Recordings Analyzed**: `24`
- **3x Repeatability (Deterministic)**: `24/24` (`100.0%`)

## Audio Signal Summary

- **Containers / Codecs**: `['matroska,webm']` / `['opus']`
- **Native Sample Rates / Channels**: `[48000]` Hz / `[1]` ch
- **Avg Total Duration**: `3.8625 s` (Speech: `1.7153 s`, Silence: `55.3204%`)
- **Avg Leading / Trailing Silence**: `1.2293 s` / `0.9178 s`
- **Avg RMS / Peak / Est. SNR**: `0.0366` (`-28.8438 dBFS`) / `0.3007` (`-10.5954 dBFS`) / `31.2533 dB`
- **Max Clipping Fraction**: `0.0`

## Microphone vs Technical Recognition Diagnosis

- **Normal English (`E`, `F`)**: raw term accuracy `83.3%`, avg RMS `-28.7367 dBFS`, SNR `26.235 dB`
- **Technical Queries (`A–D`, `G–H`)**: raw term accuracy `38.9%`, avg RMS `-28.8794 dBFS`, SNR `32.9261 dB`

## Required Comparison Table (Raw STT Recognition & Latency)

| Configuration | TCP | SYN | SYN Flood | DDoS | TCB | Normal English | Retrieval Success | Avg latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Current | 66.7% | 0.0% | 0.0% | 100.0% | 66.7% | 83.3% | 83.3% | 1230.8 ms |
| VAD | 100.0% | 0.0% | 0.0% | 100.0% | 66.7% | 100.0% | 87.5% | 1238.3 ms |
| VAD_Default_050 | 66.7% | 0.0% | 0.0% | 100.0% | 66.7% | 100.0% | 83.3% | 1230.1 ms |
| Normalized | 66.7% | 0.0% | 0.0% | 100.0% | 66.7% | 83.3% | 83.3% | 1231.9 ms |
| VAD + normalized | 100.0% | 0.0% | 0.0% | 100.0% | 66.7% | 100.0% | 87.5% | 1233.4 ms |
| Whisper_Beam5 | 66.7% | 0.0% | 0.0% | 100.0% | 66.7% | 100.0% | 87.5% | 1257.9 ms |
| Whisper_Temp0 | 66.7% | 0.0% | 0.0% | 100.0% | 66.7% | 83.3% | 83.3% | 1226.7 ms |
| Whisper_NoCondPrev | 66.7% | 0.0% | 0.0% | 100.0% | 66.7% | 83.3% | 83.3% | 1234.0 ms |
| Whisper_Temp0_NoCond | 66.7% | 0.0% | 0.0% | 100.0% | 66.7% | 83.3% | 83.3% | 1236.2 ms |
| Alt_VAD_MinSil500 | 66.7% | 0.0% | 0.0% | 100.0% | 66.7% | 83.3% | 83.3% | 1236.4 ms |
| Whisper_SoftVAD_035 | 66.7% | 0.0% | 0.0% | 100.0% | 66.7% | 83.3% | 79.2% | 1229.9 ms |
| Whisper_NoVAD | 100.0% | 0.0% | 0.0% | 100.0% | 66.7% | 100.0% | 79.2% | 1402.8 ms |
| Whisper_Tuned | 66.7% | 0.0% | 0.0% | 66.7% | 66.7% | 100.0% | 83.3% | 1284.6 ms |
| Document prompt | 100.0% | 100.0% | 50.0% | 100.0% | 66.7% | 100.0% | 95.8% | 1272.6 ms |
| Document_Prompt_NetOnly | 100.0% | 100.0% | 50.0% | 100.0% | 66.7% | 100.0% | 91.7% | 1282.0 ms |
| Document_Hotwords | 100.0% | 100.0% | 33.3% | 100.0% | 66.7% | 100.0% | 83.3% | 1251.5 ms |
| Document_Prompt_Tuned | 66.7% | 100.0% | 50.0% | 100.0% | 66.7% | 100.0% | 83.3% | 1295.2 ms |
| Mono_BestCh | 66.7% | 0.0% | 0.0% | 100.0% | 66.7% | 100.0% | 83.3% | 1252.8 ms |
| Resample_Float | 66.7% | 0.0% | 0.0% | 100.0% | 66.7% | 100.0% | 83.3% | 1223.5 ms |

## Comparison Table After Phase 2 Recovery

| Configuration | Raw Tech Term | Post-Recovery Tech Term | Post-Recovery Acronym | Grounded Avail | Hallucinations (E/F) |
|---|---:|---:|---:|---:|---:|
| Current | 38.9% | 66.7% | 60.0% | 83.3% | 0 |
| VAD | 44.4% | 72.2% | 66.7% | 87.5% | 0 |
| VAD_Default_050 | 38.9% | 66.7% | 60.0% | 83.3% | 0 |
| Normalized | 38.9% | 72.2% | 66.7% | 83.3% | 0 |
| VAD + normalized | 44.4% | 77.8% | 73.3% | 87.5% | 0 |
| Whisper_Beam5 | 38.9% | 66.7% | 60.0% | 87.5% | 0 |
| Whisper_Temp0 | 38.9% | 66.7% | 60.0% | 83.3% | 0 |
| Whisper_NoCondPrev | 38.9% | 66.7% | 60.0% | 83.3% | 0 |
| Whisper_Temp0_NoCond | 38.9% | 66.7% | 60.0% | 83.3% | 0 |
| Alt_VAD_MinSil500 | 38.9% | 66.7% | 60.0% | 83.3% | 0 |
| Whisper_SoftVAD_035 | 38.9% | 61.1% | 60.0% | 79.2% | 0 |
| Whisper_NoVAD | 44.4% | 66.7% | 66.7% | 79.2% | 0 |
| Whisper_Tuned | 33.3% | 61.1% | 53.3% | 83.3% | 0 |
| Document prompt | 77.8% | 83.3% | 80.0% | 95.8% | 0 |
| Document_Prompt_NetOnly | 77.8% | 83.3% | 80.0% | 91.7% | 0 |
| Document_Hotwords | 72.2% | 77.8% | 73.3% | 83.3% | 0 |
| Document_Prompt_Tuned | 72.2% | 77.8% | 73.3% | 83.3% | 0 |
| Mono_BestCh | 38.9% | 61.1% | 60.0% | 83.3% | 0 |
| Resample_Float | 38.9% | 61.1% | 60.0% | 83.3% | 0 |

## Per-Recording Transcripts & Recovery Detail (`Current` vs `VAD + normalized` vs `Document prompt`)

| Clip | Target | Dur (Speech) | SNR dB | Det? | Current Raw | Post-P2 Recovered | Retrieval |
|---|---|---:|---:|---|---|---|---|
| `a_1` | What is TCP? | 5.28s (1.57s) | 36.3 | YES | 'What is TCP?' | 'What is TCP?' (UNCHANGED) | PASS (0.87) |
| `a_2` | What is TCP? | 3.96s (1.09s) | 27.3 | YES | 'What does TCB?' | 'What does TCB?' (UNCHANGED) | PASS (0.74) |
| `a_3` | What is TCP? | 4.74s (1.89s) | 27.3 | YES | 'What is TCP?' | 'What is TCP?' (UNCHANGED) | PASS (0.87) |
| `b_1` | What is SYN? | 3.54s (1.41s) | 33.4 | YES | 'What is sin?' | 'What is sin?' (SUGGESTED) | FAIL (0.00) |
| `b_2` | What is SYN? | 3.78s (1.22s) | 34.9 | YES | 'What is sin?' | 'What is sin?' (SUGGESTED) | FAIL (0.00) |
| `b_3` | What is SYN? | 4.14s (1.63s) | 34.5 | YES | 'What is sin?' | 'What is sin?' (SUGGESTED) | FAIL (0.00) |
| `c_1` | What is SYN flood? | 4.08s (1.82s) | 32.9 | YES | 'What is sin flood?' | 'What is SYN flood?' (RECOVERED) | PASS (0.88) |
| `c_2` | What is SYN flood? | 4.20s (1.86s) | 35.4 | YES | 'What is sin flood?' | 'What is SYN flood?' (RECOVERED) | PASS (0.88) |
| `c_3` | What is SYN flood? | 4.26s (1.86s) | 23.3 | YES | 'What is sin flood?' | 'What is SYN flood?' (RECOVERED) | PASS (0.88) |
| `d_1` | Explain SYN flood. | 3.48s (1.28s) | 27.8 | YES | 'experiencing flood.' | 'Processing flood.' (RECOVERED) | PASS (0.54) |
| `d_2` | Explain SYN flood. | 4.20s (1.57s) | 34.7 | YES | "It's playing sin flood." | "It's playing SYN flood." (RECOVERED) | PASS (0.62) |
| `d_3` | Explain SYN flood. | 4.08s (1.73s) | 40.8 | YES | 'Explain Sing Flood.' | 'Explain Sing Flood.' (UNCHANGED) | PASS (0.42) |
| `e_1` | What is a computer? | 3.18s (1.60s) | 27.5 | YES | 'What is a computer?' | 'What is a computer?' (SUGGESTED) | PASS (0.86) |
| `e_2` | What is a computer? | 3.54s (2.29s) | 23.1 | YES | 'What is a computer?' | 'What is a computer?' (SUGGESTED) | PASS (0.86) |
| `e_3` | What is a computer? | 2.58s (1.06s) | 26.0 | YES | 'What is a computer?' | 'What is a computer?' (SUGGESTED) | PASS (0.86) |
| `f_1` | Explain computer networks. | 3.42s (1.73s) | 30.4 | YES | "It's brain computer networks" | "It's brain computer networks" (UNCHANGED) | PASS (0.43) |
| `f_2` | Explain computer networks. | 3.78s (1.86s) | 20.4 | YES | "It's playing computer networks." | "It's playing computer networks." (UNCHANGED) | PASS (0.45) |
| `f_3` | Explain computer networks. | 3.54s (1.54s) | 30.0 | YES | "It's brain computing at works." | "It's brain computing at works." (SUGGESTED) | FAIL (0.31) |
| `g_1` | What is a transmission control block? | 3.96s (1.98s) | 30.5 | YES | 'What is a trans-mission control block?' | 'What is a Transmission control block?' (RECOVERED) | PASS (0.74) |
| `g_2` | What is a transmission control block? | 4.74s (2.37s) | 33.3 | YES | 'What is a transmission control block?' | 'What is a transmission control block?' (UNCHANGED) | PASS (0.74) |
| `g_3` | What is a transmission control block? | 4.74s (2.98s) | 28.4 | YES | 'What is the transmission control block?' | 'What is the transmission control block?' (UNCHANGED) | PASS (0.71) |
| `h_1` | What is DDoS? | 2.88s (1.50s) | 41.3 | YES | 'What is DDoS?' | 'What is DDoS?' (UNCHANGED) | PASS (0.76) |
| `h_2` | What is DDoS? | 3.42s (2.08s) | 33.2 | YES | 'What is DDoS?' | 'What is DDoS?' (UNCHANGED) | PASS (0.76) |
| `h_3` | What is DDoS? | 3.18s (1.28s) | 37.5 | YES | 'What is DDOS?' | 'What is DDoS?' (RECOVERED) | PASS (0.76) |
