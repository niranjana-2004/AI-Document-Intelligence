"""
Cognidocs Voice Assistant Phase 2.1 — Non-Production STT & Audio Diagnostic Benchmark.

Measures real browser-captured audio signal properties, Silero VAD segmentation,
3x STT repeatability, microphone health vs. technical-term weakness, offline VAD/
normalization/Whisper/document-prompt experiments, and Phase 2 recovery + retrieval impact.

Strictly non-production: zero writes to dev SQLite database (uses isolated_test_db)
and zero modifications to production STT/recovery runtime behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import av
import numpy as np
from faster_whisper.vad import VadOptions, get_speech_timestamps

from app.core.config import settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.user import User
from app.services.context_service import build_context
from app.services.embedding_services import generate_embedding
from app.services.question_service import MIN_CONFIDENCE_THRESHOLD
from app.services.voice_query_recovery_service import (
    clear_voice_recovery_cache,
    recover_voice_query,
)
from app.services.voice_service import decode_audio_to_16k_mono, get_whisper_model
from app.services.voice_terminology_service import clear_voice_terminology_cache
from test_db_isolation import isolated_test_db


BENCHMARKS_DIR = Path(__file__).resolve().parent
CLIPS_DIR = BENCHMARKS_DIR / "voice_stt_diagnostic_clips"
DEFAULT_MANIFEST_PATH = BENCHMARKS_DIR / "voice_stt_diagnostic_manifest.json"
DEFAULT_RESULTS_JSON = BENCHMARKS_DIR / "voice_stt_diagnostic_results.json"
DEFAULT_RESULTS_MD = BENCHMARKS_DIR / "voice_stt_diagnostic.md"

SAMPLE_RATE = 16000

DIAGNOSTIC_PROMPTS: list[dict[str, Any]] = [
    {
        "group": "A",
        "text": "What is TCP?",
        "category": "acronym",
        "column": "TCP",
        "required_terms": ["tcp"],
        "is_normal_english": False,
        "expected_doc_tag": "net_ref",
    },
    {
        "group": "B",
        "text": "What is SYN?",
        "category": "acronym",
        "column": "SYN",
        "required_terms": ["syn"],
        "is_normal_english": False,
        "expected_doc_tag": "net_ref",
    },
    {
        "group": "C",
        "text": "What is SYN flood?",
        "category": "acronym_compound",
        "column": "SYN Flood",
        "required_terms": ["syn", "flood"],
        "is_normal_english": False,
        "expected_doc_tag": "net_ref",
    },
    {
        "group": "D",
        "text": "Explain SYN flood.",
        "category": "acronym_compound",
        "column": "SYN Flood",
        "required_terms": ["syn", "flood"],
        "is_normal_english": False,
        "expected_doc_tag": "net_ref",
    },
    {
        "group": "E",
        "text": "What is a computer?",
        "category": "normal_english",
        "column": "Normal English",
        "required_terms": ["computer"],
        "is_normal_english": True,
        "expected_doc_tag": "cs_ref",
    },
    {
        "group": "F",
        "text": "Explain computer networks.",
        "category": "normal_english",
        "column": "Normal English",
        "required_terms": ["computer", "network"],
        "is_normal_english": True,
        "expected_doc_tag": "cs_ref",
    },
    {
        "group": "G",
        "text": "What is a transmission control block?",
        "category": "technical_phrase",
        "column": "TCB",
        "required_terms": ["transmission", "control", "block"],
        "is_normal_english": False,
        "expected_doc_tag": "net_ref",
    },
    {
        "group": "H",
        "text": "What is DDoS?",
        "category": "acronym",
        "column": "DDoS",
        "required_terms": ["ddos"],
        "is_normal_english": False,
        "expected_doc_tag": "net_ref",
    },
]

DOCUMENT_AWARE_PROMPT = (
    "Computer Networks terminology: "
    "TCP, SYN, SYN flood, RST, TCB, transmission control block, DDoS, RFC 5961."
)
DOCUMENT_HOTWORDS = "TCP SYN SYN flood RST TCB DDoS RFC 5961"


# ---------------------------------------------------------------------------
# Audio inspection & preprocessing helpers (experimental / read-only)
# ---------------------------------------------------------------------------

def probe_container_metadata(audio_path: Path) -> dict[str, Any]:
    """Inspect audio container format, stream codec, native sample rate, and channels via PyAV."""
    meta: dict[str, Any] = {
        "file_size_bytes": audio_path.stat().st_size if audio_path.exists() else 0,
        "container_format": None,
        "container_duration_s": None,
        "codec": None,
        "native_sample_rate": None,
        "channels": None,
        "bit_rate": None,
    }
    try:
        with av.open(str(audio_path), mode="r") as container:
            meta["container_format"] = container.format.name if container.format else None
            if container.duration and container.duration > 0:
                meta["container_duration_s"] = round(float(container.duration) / float(av.time_base), 4)
            audio_streams = [s for s in container.streams if s.type == "audio"]
            if audio_streams:
                st = audio_streams[0]
                cc = st.codec_context
                meta["codec"] = getattr(cc, "name", None)
                meta["native_sample_rate"] = getattr(cc, "sample_rate", None)
                meta["channels"] = getattr(cc, "channels", None)
                meta["bit_rate"] = getattr(cc, "bit_rate", None)
    except Exception as exc:
        meta["probe_error"] = str(exc)
    return meta


def decode_audio_float_resampler(audio_path: Path) -> np.ndarray:
    """Alternative PyAV decode using fltp 16kHz mono (without intermediate s16 quantization)."""
    resampler = av.audio.resampler.AudioResampler(
        format="flt",
        layout="mono",
        rate=SAMPLE_RATE,
    )
    chunks: list[np.ndarray] = []
    with av.open(str(audio_path), mode="r") as container:
        for frame in container.decode(audio=0):
            for resampled in resampler.resample(frame):
                arr = resampled.to_ndarray()
                if arr.size:
                    chunks.append(arr.reshape(-1).astype(np.float32))
        for resampled in resampler.resample(None):
            arr = resampled.to_ndarray()
            if arr.size:
                chunks.append(arr.reshape(-1).astype(np.float32))
    if not chunks:
        return np.array([], dtype=np.float32)
    return np.clip(np.concatenate(chunks), -1.0, 1.0)


def decode_audio_channel_selected(audio_path: Path) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Decode native channels before downmixing to inspect stereo imbalance / phase cancellation
    vs direct PyAV mono downmix.
    """
    raw_frames: list[np.ndarray] = []
    in_rate = SAMPLE_RATE
    with av.open(str(audio_path), mode="r") as container:
        stream = [s for s in container.streams if s.type == "audio"][0]
        in_rate = stream.codec_context.sample_rate or SAMPLE_RATE
        for frame in container.decode(audio=0):
            arr = frame.to_ndarray()
            if arr.ndim == 1:
                arr = arr[np.newaxis, :]
            elif arr.shape[0] > 8 and arr.shape[1] <= 8:
                # Planar vs packed detection: ensure shape (channels, samples)
                arr = arr.T
            if arr.dtype == np.int16:
                arr = arr.astype(np.float32) / 32768.0
            elif arr.dtype == np.int32:
                arr = arr.astype(np.float32) / 2147483648.0
            else:
                arr = arr.astype(np.float32)
            raw_frames.append(arr)

    if not raw_frames:
        return np.array([], dtype=np.float32), {"channels": 0, "native_rate": in_rate}

    stacked = np.concatenate(raw_frames, axis=1)
    n_ch = stacked.shape[0]
    channel_rms = [round(float(np.sqrt(np.mean(np.square(stacked[c])))), 6) for c in range(n_ch)]
    # Pick loudest channel when multi-channel, then resample to 16k mono via PyAV
    best_ch = int(np.argmax(channel_rms))
    mono_native = np.clip(stacked[best_ch], -1.0, 1.0)

    if in_rate == SAMPLE_RATE:
        return mono_native.astype(np.float32), {"channels": n_ch, "channel_rms": channel_rms, "picked_channel": best_ch}

    resampler = av.audio.resampler.AudioResampler(format="flt", layout="mono", rate=SAMPLE_RATE)
    frame = av.AudioFrame.from_ndarray(mono_native.reshape(1, -1), format="fltp", layout="mono")
    frame.sample_rate = in_rate
    out_chunks = []
    for resampled in resampler.resample(frame):
        out_chunks.append(resampled.to_ndarray().reshape(-1).astype(np.float32))
    for resampled in resampler.resample(None):
        out_chunks.append(resampled.to_ndarray().reshape(-1).astype(np.float32))
    out = np.concatenate(out_chunks) if out_chunks else np.array([], dtype=np.float32)
    return np.clip(out, -1.0, 1.0), {
        "channels": n_ch,
        "channel_rms": channel_rms,
        "picked_channel": best_ch,
    }


def trim_silence_vad(
    audio: np.ndarray,
    threshold: float = 0.5,
    speech_pad_ms: int = 300,
    min_speech_duration_ms: int = 100,
    min_silence_duration_ms: int = 800,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Trim leading/trailing silence (and long dead air) using Silero VAD timestamps."""
    t0 = time.perf_counter()
    if audio.size == 0:
        return audio, {"segments": 0, "speech_s": 0.0, "preprocess_ms": 0.0}

    opts = VadOptions(
        threshold=threshold,
        min_speech_duration_ms=min_speech_duration_ms,
        min_silence_duration_ms=min_silence_duration_ms,
        speech_pad_ms=0,
    )
    chunks = get_speech_timestamps(audio, vad_options=opts, sampling_rate=SAMPLE_RATE)
    if not chunks:
        return audio, {
            "segments": 0,
            "speech_s": 0.0,
            "leading_trimmed_s": 0.0,
            "trailing_trimmed_s": 0.0,
            "fallback_untrimmed": True,
            "preprocess_ms": round((time.perf_counter() - t0) * 1000.0, 2),
        }

    pad_samples = int((speech_pad_ms / 1000.0) * SAMPLE_RATE)
    start = max(0, int(chunks[0]["start"]) - pad_samples)
    end = min(len(audio), int(chunks[-1]["end"]) + pad_samples)
    trimmed = audio[start:end]
    speech_samples = sum(max(0, c["end"] - c["start"]) for c in chunks)
    return trimmed.astype(np.float32), {
        "segments": len(chunks),
        "speech_s": round(speech_samples / float(SAMPLE_RATE), 4),
        "trimmed_duration_s": round(len(trimmed) / float(SAMPLE_RATE), 4),
        "leading_trimmed_s": round(start / float(SAMPLE_RATE), 4),
        "trailing_trimmed_s": round((len(audio) - end) / float(SAMPLE_RATE), 4),
        "fallback_untrimmed": False,
        "preprocess_ms": round((time.perf_counter() - t0) * 1000.0, 2),
    }


def normalize_amplitude(audio: np.ndarray, target_peak: float = 0.707, target_rms: float = 0.10) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Experimental gentle AGC / peak+RMS normalization capped below clipping and bounded gain
    so pure background noise isn't amplified > 20x.
    """
    t0 = time.perf_counter()
    if audio.size == 0:
        return audio, {"gain_applied": 1.0, "preprocess_ms": 0.0}

    dc_removed = audio - float(np.mean(audio))
    rms = float(np.sqrt(np.mean(np.square(dc_removed))))
    peak = float(np.max(np.abs(dc_removed)))
    if peak < 1e-6 or rms < 1e-6:
        return dc_removed.astype(np.float32), {"gain_applied": 1.0, "preprocess_ms": 0.0}

    desired_rms_gain = target_rms / rms
    max_safe_peak_gain = target_peak / peak
    # Never boost background-only hiss by > 12x (~21.5 dB), and never clip above target_peak
    gain = min(desired_rms_gain, max_safe_peak_gain, 12.0)
    if gain < 1.0 and peak <= 0.92:
        # Don't attenuate healthy signals unless near clipping
        gain = 1.0

    normed = np.clip(dc_removed * gain, -0.98, 0.98).astype(np.float32)
    return normed, {
        "gain_applied": round(float(gain), 3),
        "gain_db": round(20.0 * math.log10(max(gain, 1e-6)), 2),
        "post_rms": round(float(np.sqrt(np.mean(np.square(normed)))), 6),
        "post_peak": round(float(np.max(np.abs(normed))), 6),
        "preprocess_ms": round((time.perf_counter() - t0) * 1000.0, 2),
    }


def measure_audio_diagnostics(
    audio_path: str | Path,
    frontend_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Section 2: Measure real audio properties for a recorded voice file using PyAV + Silero VAD.
    """
    path = Path(audio_path)
    container_meta = probe_container_metadata(path)
    audio_16k = decode_audio_to_16k_mono(str(path))
    n_samples = len(audio_16k)
    pcm_duration_s = round(float(n_samples) / float(SAMPLE_RATE), 4) if n_samples else 0.0

    if n_samples == 0:
        return {
            **container_meta,
            "decoded_pcm_duration_s": 0.0,
            "speech_duration_s": 0.0,
            "leading_silence_s": 0.0,
            "trailing_silence_s": 0.0,
            "silence_pct": 100.0,
            "rms_energy": 0.0,
            "rms_dbfs": -120.0,
            "peak_amplitude": 0.0,
            "peak_dbfs": -120.0,
            "noise_floor_rms": 0.0,
            "speech_rms": 0.0,
            "estimated_snr_db": 0.0,
            "clipping_fraction": 0.0,
            "vad_segments_default": [],
            "vad_segments_soft": [],
            "frontend_meta": frontend_meta or {},
        }

    rms = float(np.sqrt(np.mean(np.square(audio_16k))))
    peak = float(np.max(np.abs(audio_16k)))
    clip_frac = float(np.mean(np.abs(audio_16k) >= 0.985))

    # Production Silero VAD bounds (includes faster-whisper default 400ms speech_pad_ms)
    vad_default = get_speech_timestamps(
        audio_16k,
        vad_options=VadOptions(threshold=0.5, min_speech_duration_ms=0, min_silence_duration_ms=2000, speech_pad_ms=400),
        sampling_rate=SAMPLE_RATE,
    )
    # True unpadded acoustic speech bounds (speech_pad_ms=0)
    vad_unpadded = get_speech_timestamps(
        audio_16k,
        vad_options=VadOptions(threshold=0.5, min_speech_duration_ms=60, min_silence_duration_ms=600, speech_pad_ms=0),
        sampling_rate=SAMPLE_RATE,
    )
    # Soft unpadded Silero VAD estimate for low-energy onset visibility
    vad_soft = get_speech_timestamps(
        audio_16k,
        vad_options=VadOptions(threshold=0.35, min_speech_duration_ms=80, min_silence_duration_ms=600, speech_pad_ms=0),
        sampling_rate=SAMPLE_RATE,
    )

    active_vad = vad_unpadded if vad_unpadded else vad_soft
    speech_samples = sum(max(0, int(c["end"]) - int(c["start"])) for c in active_vad)
    speech_dur_s = round(float(speech_samples) / float(SAMPLE_RATE), 4)
    leading_s = round(float(active_vad[0]["start"]) / float(SAMPLE_RATE), 4) if active_vad else pcm_duration_s
    trailing_s = round(float(max(0, n_samples - int(active_vad[-1]["end"]))) / float(SAMPLE_RATE), 4) if active_vad else 0.0
    silence_pct = round(100.0 * max(0.0, pcm_duration_s - speech_dur_s) / max(pcm_duration_s, 1e-6), 2)

    # Estimate speech vs noise RMS across 20ms frames using VAD mask
    speech_mask = np.zeros(n_samples, dtype=bool)
    for seg in (vad_soft or active_vad):
        speech_mask[max(0, int(seg["start"])):min(n_samples, int(seg["end"]))] = True

    if np.any(speech_mask):
        speech_rms = float(np.sqrt(np.mean(np.square(audio_16k[speech_mask]))))
    else:
        speech_rms = rms

    non_speech_mask = ~speech_mask
    if np.sum(non_speech_mask) >= int(0.1 * SAMPLE_RATE):
        # Compute 20ms frame RMS percentiles for noise floor robustness
        frame_len = int(0.02 * SAMPLE_RATE)
        ns_samples = audio_16k[non_speech_mask]
        n_frames = len(ns_samples) // frame_len
        if n_frames >= 3:
            frames = ns_samples[: n_frames * frame_len].reshape(n_frames, frame_len)
            frame_rms = np.sqrt(np.mean(np.square(frames), axis=1))
            noise_floor_rms = float(np.percentile(frame_rms, 50))
        else:
            noise_floor_rms = float(np.sqrt(np.mean(np.square(ns_samples))))
    else:
        # Estimate bottom 15th percentile frame RMS when speech spans entire file
        frame_len = int(0.02 * SAMPLE_RATE)
        n_frames = max(1, n_samples // frame_len)
        frames = audio_16k[: n_frames * frame_len].reshape(n_frames, frame_len)
        frame_rms = np.sqrt(np.mean(np.square(frames), axis=1))
        noise_floor_rms = float(np.percentile(frame_rms, 15))

    snr_db = 20.0 * math.log10(max(speech_rms, 1e-7) / max(noise_floor_rms, 1e-7))

    # Channel inspection if multi-channel
    _, chan_info = decode_audio_channel_selected(path)

    return {
        **container_meta,
        "decoded_pcm_duration_s": pcm_duration_s,
        "speech_duration_s": speech_dur_s,
        "leading_silence_s": leading_s,
        "trailing_silence_s": trailing_s,
        "silence_pct": silence_pct,
        "rms_energy": round(rms, 6),
        "rms_dbfs": round(20.0 * math.log10(max(rms, 1e-7)), 2),
        "peak_amplitude": round(peak, 6),
        "peak_dbfs": round(20.0 * math.log10(max(peak, 1e-7)), 2),
        "speech_rms": round(speech_rms, 6),
        "noise_floor_rms": round(noise_floor_rms, 6),
        "estimated_snr_db": round(snr_db, 2),
        "clipping_fraction": round(clip_frac, 6),
        "vad_segments_default": [
            {"start_s": round(s["start"] / SAMPLE_RATE, 3), "end_s": round(s["end"] / SAMPLE_RATE, 3)}
            for s in vad_default
        ],
        "vad_segments_soft": [
            {"start_s": round(s["start"] / SAMPLE_RATE, 3), "end_s": round(s["end"] / SAMPLE_RATE, 3)}
            for s in vad_soft
        ],
        "channel_probe": chan_info,
        "frontend_meta": frontend_meta or {},
    }


# ---------------------------------------------------------------------------
# Transcript evaluation helpers
# ---------------------------------------------------------------------------

def _norm_tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _canonical_norm_str(text: str) -> str:
    return " ".join(_norm_tokens(text))


def _contains_term_sequence(tokens: list[str], required_terms: list[str]) -> bool:
    joined = " ".join(tokens)
    compact = "".join(tokens)
    for term in required_terms:
        t = term.lower()
        # Allow minor pluralization ("networks" contains "network") and joined spaced acronyms ("s y n" -> "syn")
        if t == "tcp":
            if "tcp" not in tokens and "t c p" not in joined and "tcp" not in compact:
                return False
        elif t == "syn":
            if "syn" not in tokens and "s y n" not in joined:
                return False
        elif t == "ddos":
            if "ddos" not in tokens and "d d o s" not in joined and "ddos" not in compact:
                return False
        elif t == "flood":
            if not any(tok.startswith("flood") for tok in tokens):
                return False
        elif t == "network":
            if not any(tok.startswith("network") for tok in tokens):
                return False
        else:
            if t not in tokens and not any(tok.startswith(t) for tok in tokens):
                return False
    return True


def score_transcript_against_prompt(transcript: str, prompt_spec: dict[str, Any]) -> dict[str, Any]:
    """Compute exact sentence match, technical/keyword term match, and strict acronym match."""
    expected = prompt_spec["text"]
    exact_match = _canonical_norm_str(transcript) == _canonical_norm_str(expected)
    tokens = _norm_tokens(transcript)
    term_hit = _contains_term_sequence(tokens, prompt_spec["required_terms"])

    # Strict acronym hit checks that target acronyms appear coherently (without spaces/misspellings)
    acronym_required = [t for t in prompt_spec["required_terms"] if t in ("tcp", "syn", "ddos")]
    if acronym_required:
        acronym_exact = all(t in tokens for t in acronym_required)
    else:
        acronym_exact = None

    # Hallucination check on Normal English (did technical prompt inject TCP/SYN/DDoS/RFC?)
    injected_tech = False
    if prompt_spec["is_normal_english"]:
        exp_set = set(_norm_tokens(expected))
        extra = set(tokens) - exp_set
        if extra & {"tcp", "syn", "flood", "ddos", "tcb", "rst", "rfc", "5961"}:
            injected_tech = True

    return {
        "exact_sentence": exact_match,
        "term_hit": term_hit,
        "acronym_exact": acronym_exact,
        "injected_tech_hallucination": injected_tech,
    }


def run_whisper_transcribe(
    model: Any,
    audio_array: np.ndarray,
    **transcribe_kwargs: Any,
) -> dict[str, Any]:
    """Run local faster-whisper on an in-memory 16kHz mono float32 waveform and time it cleanly."""
    if audio_array is None or len(audio_array) == 0:
        return {"text": "", "latency_ms": 0.0, "avg_logprob": None, "no_speech_prob": None, "segments": []}

    t0 = time.perf_counter()
    segments_gen, info = model.transcribe(audio_array, **transcribe_kwargs)
    segs = list(segments_gen)
    latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    text = " ".join(s.text.strip() for s in segs if s.text).strip()
    avg_lp = round(sum(float(getattr(s, "avg_logprob", 0.0)) for s in segs) / len(segs), 4) if segs else None
    max_ns = round(max(float(getattr(s, "no_speech_prob", 0.0)) for s in segs), 4) if segs else None
    return {
        "text": text,
        "latency_ms": latency_ms,
        "language": getattr(info, "language", "en"),
        "avg_logprob": avg_lp,
        "no_speech_prob": max_ns,
        "segments": [
            {
                "start": round(float(s.start), 3),
                "end": round(float(s.end), 3),
                "text": s.text.strip(),
                "avg_logprob": round(float(s.avg_logprob), 4),
                "no_speech_prob": round(float(s.no_speech_prob), 4),
                "compression_ratio": round(float(s.compression_ratio), 4),
            }
            for s in segs
        ],
    }


# ---------------------------------------------------------------------------
# Isolated DB fixture for Section 10 (Phase 2 recovery + retrieval check)
# ---------------------------------------------------------------------------

def _setup_isolated_diagnostic_docs(db) -> tuple[int, list[int], dict[str, int]]:
    user = db.query(User).filter(User.id == 4).first() or db.query(User).first()
    user_id = user.id

    net_pages = [
        (
            1,
            "TCP (Transmission Control Protocol) is a connection-oriented transport protocol that guarantees reliable, in-order byte delivery using a three-way handshake (SYN, SYN-ACK, ACK) and RST packets for abrupt resets.",
        ),
        (
            2,
            "A SYN flood is a denial-of-service (DoS) and DDoS attack that exploits the TCP three-way handshake by sending numerous spoofed SYN packets to exhaust half-open server backlog queues.",
        ),
        (
            3,
            "A Transmission Control Block (TCB) is the operating system kernel data structure storing the state, sequence numbers, timers, and buffers for each TCP connection. SYN cookies help protect TCB allocation during DDoS and RFC 5961 hardening.",
        ),
    ]
    cs_pages = [
        (
            1,
            "A computer is a programmable electronic machine that accepts input, stores data, processes instructions in the CPU and memory, and produces output.",
        ),
        (
            2,
            "Computer networks connect multiple computing devices across local and wide area links using packet switching, routers, and layered protocols to exchange data reliably.",
        ),
    ]

    net_doc = Document(
        user_id=user_id,
        filename="Computer_Networks_TCP_Reference.txt",
        document_type="TXT",
        file_path="diagnostic/net_ref.txt",
        extracted_text="\n\n".join(p[1] for p in net_pages),
        text_length=sum(len(p[1]) for p in net_pages),
        processing_status="ready",
        processing_progress=100,
    )
    cs_doc = Document(
        user_id=user_id,
        filename="Computer_Fundamentals_and_Networks.txt",
        document_type="TXT",
        file_path="diagnostic/cs_ref.txt",
        extracted_text="\n\n".join(p[1] for p in cs_pages),
        text_length=sum(len(p[1]) for p in cs_pages),
        processing_status="ready",
        processing_progress=100,
    )
    db.add_all([net_doc, cs_doc])
    db.flush()

    for idx, (pg, content) in enumerate(net_pages):
        db.add(
            DocumentChunk(
                document_id=net_doc.id,
                chunk_index=idx,
                page_number=pg,
                content=content,
                embedding=generate_embedding(content),
            )
        )
    for idx, (pg, content) in enumerate(cs_pages):
        db.add(
            DocumentChunk(
                document_id=cs_doc.id,
                chunk_index=idx,
                page_number=pg,
                content=content,
                embedding=generate_embedding(content),
            )
        )

    # Also include existing Doc #12 (handwritten SYN flood) if owned by this user
    scope_ids = [net_doc.id, cs_doc.id]
    doc12 = db.query(Document).filter(Document.id == 12, Document.user_id == user_id).first()
    if doc12 is not None:
        scope_ids.append(doc12.id)

    db.commit()
    tag_map = {"net_ref": net_doc.id, "cs_ref": cs_doc.id}
    return user_id, scope_ids, tag_map


def evaluate_phase2_and_retrieval(
    raw_text: str,
    prompt_spec: dict[str, Any],
    db,
    user_id: int,
    scope_ids: list[int],
    tag_map: dict[str, int],
) -> dict[str, Any]:
    """Run Section 10: Phase 2 recovery + grounded retrieval (with raw fallback check)."""
    if not raw_text or not raw_text.strip():
        return {
            "raw_transcript": raw_text,
            "recovered_transcript": "",
            "decision": "UNCHANGED",
            "recovery_applied": False,
            "recovery_confidence": 0.0,
            "effective_query": "",
            "retrieval_success": False,
            "top_score": 0.0,
            "top_similarity": 0.0,
            "top_source": None,
            "expected_source_hit": False,
            "grounded_available": False,
        }

    rec = recover_voice_query(
        raw_transcript=raw_text,
        db=db,
        user_id=user_id,
        document_ids=scope_ids,
    )
    if rec.decision.value == "RECOVERED" and rec.recovery_applied:
        active_query = rec.recovered_transcript
    else:
        active_query = rec.raw_transcript

    ctx = build_context(
        query=active_query,
        db=db,
        document_ids=scope_ids,
        top_k=5,
        user_id=user_id,
    )
    top_score = float(ctx["results"][0].get("final_score", 0.0)) if ctx["results"] else 0.0
    fallback_used = False
    if (ctx["result_count"] == 0 or top_score < MIN_CONFIDENCE_THRESHOLD) and active_query.lower() != raw_text.strip().lower():
        raw_ctx = build_context(query=raw_text, db=db, document_ids=scope_ids, top_k=5, user_id=user_id)
        raw_score = float(raw_ctx["results"][0].get("final_score", 0.0)) if raw_ctx["results"] else 0.0
        if raw_ctx["result_count"] > 0 and raw_score >= MIN_CONFIDENCE_THRESHOLD and raw_score > top_score:
            ctx = raw_ctx
            top_score = raw_score
            active_query = raw_text
            fallback_used = True

    top_res = ctx["results"][0] if ctx["results"] else None
    expected_doc_id = tag_map.get(prompt_spec["expected_doc_tag"])
    doc_ids_hit = [r.get("document_id") for r in ctx["results"]]
    if prompt_spec["expected_doc_tag"] == "net_ref" and any(d in doc_ids_hit for d in (expected_doc_id, 12)):
        exp_hit = True
    else:
        exp_hit = expected_doc_id in doc_ids_hit

    retrieval_ok = bool(ctx["result_count"] > 0 and top_score >= MIN_CONFIDENCE_THRESHOLD)
    return {
        "raw_transcript": raw_text,
        "recovered_transcript": rec.recovered_transcript,
        "decision": rec.decision.value,
        "recovery_applied": rec.recovery_applied,
        "recovery_confidence": round(float(rec.confidence), 4),
        "effective_query": active_query,
        "retrieval_fallback_used": fallback_used,
        "retrieval_success": retrieval_ok,
        "top_score": round(top_score, 4),
        "top_similarity": round(float(top_res.get("similarity", 0.0)) if top_res else 0.0, 4),
        "top_source": f"{top_res.get('document_name')} p.{top_res.get('page_number')}" if top_res else None,
        "expected_source_hit": exp_hit,
        "grounded_available": bool(retrieval_ok and exp_hit),
    }


# ---------------------------------------------------------------------------
# Benchmark orchestration
# ---------------------------------------------------------------------------

def _prompt_lookup() -> dict[str, dict[str, Any]]:
    return {p["group"]: p for p in DIAGNOSTIC_PROMPTS}


def _pct(num: int, den: int) -> float | None:
    if den == 0:
        return None
    return round(100.0 * num / den, 1)


def run_diagnostic(manifest_path: Path, results_json_path: Path, results_md_path: Path) -> dict[str, Any]:
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Manifest not found at {manifest_path}. Record or populate diagnostic recordings first."
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    recordings = manifest.get("recordings", [])
    if not recordings:
        raise ValueError("Manifest contains 0 recordings. Capture the diagnostic clips first.")

    model = get_whisper_model()
    prompt_by_group = _prompt_lookup()

    clear_voice_terminology_cache()
    clear_voice_recovery_cache()

    clip_records: list[dict[str, Any]] = []

    with isolated_test_db(clone_dev_db=True) as (db, _, _):
        user_id, scope_ids, tag_map = _setup_isolated_diagnostic_docs(db)

        for idx, entry in enumerate(recordings, start=1):
            rel_path = entry["file_path"]
            audio_path = (BENCHMARKS_DIR / rel_path) if not Path(rel_path).is_absolute() else Path(rel_path)
            group = entry["group"]
            prompt_spec = prompt_by_group[group]

            print(f"[{idx}/{len(recordings)}] Analyzing {entry['clip_id']} ({group}: {prompt_spec['text']}) -> {audio_path.name}")

            audio_diag = measure_audio_diagnostics(audio_path, frontend_meta=entry.get("frontend_meta"))

            # Pre-decode streams used across Sections 4, 6, 7, 8, 9
            pcm_s16 = decode_audio_to_16k_mono(str(audio_path))
            pcm_flt = decode_audio_float_resampler(audio_path)
            pcm_best_ch, _ = decode_audio_channel_selected(audio_path)
            pcm_vad_soft, vad_soft_meta = trim_silence_vad(pcm_s16, threshold=0.35, speech_pad_ms=300, min_speech_duration_ms=80, min_silence_duration_ms=700)
            pcm_vad_def, vad_def_meta = trim_silence_vad(pcm_s16, threshold=0.50, speech_pad_ms=250, min_speech_duration_ms=100, min_silence_duration_ms=800)
            pcm_norm, norm_meta = normalize_amplitude(pcm_s16)
            pcm_vad_norm, vad_norm_meta = normalize_amplitude(pcm_vad_soft)

            # Section 4: Repeatability test (exact same audio 3x through production Whisper params)
            repeat_runs = []
            for r_i in range(3):
                run_res = run_whisper_transcribe(model, pcm_s16, language="en", beam_size=2, vad_filter=True)
                repeat_runs.append(run_res)
            repeat_texts = [r["text"] for r in repeat_runs]
            is_deterministic = len(set(repeat_texts)) == 1
            baseline_run = repeat_runs[0]

            # Variants dictionary (key -> dict with text, latencies, preprocess_ms, kwargs)
            variants_spec: list[tuple[str, np.ndarray, float, dict[str, Any]]] = [
                ("Current", pcm_s16, 0.0, {"language": "en", "beam_size": 2, "vad_filter": True}),
                ("Mono_BestCh", pcm_best_ch, 0.0, {"language": "en", "beam_size": 2, "vad_filter": True}),
                ("Resample_Float", pcm_flt, 0.0, {"language": "en", "beam_size": 2, "vad_filter": True}),
                ("VAD_Default_050", pcm_vad_def, vad_def_meta["preprocess_ms"], {"language": "en", "beam_size": 2, "vad_filter": False}),
                ("VAD", pcm_vad_soft, vad_soft_meta["preprocess_ms"], {"language": "en", "beam_size": 2, "vad_filter": False}),
                ("Normalized", pcm_norm, norm_meta["preprocess_ms"], {"language": "en", "beam_size": 2, "vad_filter": True}),
                (
                    "VAD + normalized",
                    pcm_vad_norm,
                    round(vad_soft_meta["preprocess_ms"] + vad_norm_meta["preprocess_ms"], 2),
                    {"language": "en", "beam_size": 2, "vad_filter": False},
                ),
                ("Whisper_Beam5", pcm_s16, 0.0, {"language": "en", "beam_size": 5, "vad_filter": True}),
                (
                    "Whisper_Temp0_NoCond",
                    pcm_s16,
                    0.0,
                    {"language": "en", "beam_size": 2, "temperature": 0.0, "condition_on_previous_text": False, "vad_filter": True},
                ),
                (
                    "Whisper_SoftVAD_035",
                    pcm_s16,
                    0.0,
                    {
                        "language": "en",
                        "beam_size": 2,
                        "vad_filter": True,
                        "vad_parameters": {"threshold": 0.35, "min_speech_duration_ms": 80, "speech_pad_ms": 400},
                    },
                ),
                ("Whisper_NoVAD", pcm_s16, 0.0, {"language": "en", "beam_size": 2, "vad_filter": False}),
                (
                    "Whisper_Tuned",
                    pcm_s16,
                    0.0,
                    {
                        "language": "en",
                        "beam_size": 5,
                        "temperature": 0.0,
                        "condition_on_previous_text": False,
                        "vad_filter": True,
                        "vad_parameters": {"threshold": 0.35, "min_speech_duration_ms": 80, "speech_pad_ms": 400},
                    },
                ),
                (
                    "Document prompt",
                    pcm_s16,
                    0.0,
                    {
                        "language": "en",
                        "beam_size": 2,
                        "vad_filter": True,
                        "initial_prompt": DOCUMENT_AWARE_PROMPT,
                    },
                ),
                (
                    "Document_Prompt_Tuned",
                    pcm_norm,
                    norm_meta["preprocess_ms"],
                    {
                        "language": "en",
                        "beam_size": 5,
                        "temperature": 0.0,
                        "condition_on_previous_text": False,
                        "vad_filter": True,
                        "vad_parameters": {"threshold": 0.35, "min_speech_duration_ms": 80, "speech_pad_ms": 400},
                        "initial_prompt": DOCUMENT_AWARE_PROMPT,
                    },
                ),
            ]

            variant_outcomes: dict[str, Any] = {}
            for cfg_name, wav_arr, prep_ms, w_kwargs in variants_spec:
                if cfg_name == "Current":
                    stt = dict(baseline_run)
                else:
                    stt = run_whisper_transcribe(model, wav_arr, **w_kwargs)
                scores = score_transcript_against_prompt(stt["text"], prompt_spec)
                p2_ret = evaluate_phase2_and_retrieval(
                    stt["text"], prompt_spec, db, user_id, scope_ids, tag_map
                )
                # Also score Phase 2 recovered transcript against target terms!
                p2_term_scores = score_transcript_against_prompt(p2_ret["effective_query"], prompt_spec)
                variant_outcomes[cfg_name] = {
                    "raw_text": stt["text"],
                    "stt_latency_ms": stt["latency_ms"],
                    "preprocess_ms": prep_ms,
                    "total_latency_ms": round(stt["latency_ms"] + prep_ms, 2),
                    "avg_logprob": stt["avg_logprob"],
                    "no_speech_prob": stt["no_speech_prob"],
                    "raw_scores": scores,
                    "post_recovery_scores": p2_term_scores,
                    "phase2_and_retrieval": p2_ret,
                }

            clip_records.append(
                {
                    "clip_id": entry["clip_id"],
                    "group": group,
                    "expected_text": prompt_spec["text"],
                    "category": prompt_spec["category"],
                    "column": prompt_spec["column"],
                    "is_normal_english": prompt_spec["is_normal_english"],
                    "file_path": rel_path,
                    "audio_diagnostics": audio_diag,
                    "vad_preprocessing_stats": {
                        "soft_035": vad_soft_meta,
                        "default_050": vad_def_meta,
                        "norm_stats": norm_meta,
                        "vad_norm_stats": vad_norm_meta,
                    },
                    "repeatability": {
                        "runs": [{"text": r["text"], "latency_ms": r["latency_ms"]} for r in repeat_runs],
                        "deterministic": is_deterministic,
                    },
                    "variants": variant_outcomes,
                }
            )

    # -----------------------------------------------------------------------
    # Aggregate metrics across configurations
    # -----------------------------------------------------------------------
    config_names = list(clip_records[0]["variants"].keys())
    summary_by_config: dict[str, Any] = {}
    for cfg in config_names:
        cols: dict[str, list[dict[str, Any]]] = defaultdict(list)
        all_items = []
        for rec in clip_records:
            v = rec["variants"][cfg]
            all_items.append((rec, v))
            cols[rec["column"]].append(v)

        def _col_term_pct(col_name: str, post_rec: bool = False) -> float | None:
            items = cols.get(col_name, [])
            if not items:
                return None
            hits = sum(
                1
                for v in items
                if (v["post_recovery_scores"]["term_hit"] if post_rec else v["raw_scores"]["term_hit"])
            )
            return _pct(hits, len(items))

        n = len(all_items)
        acronym_items = [(rec, v) for rec, v in all_items if rec["category"] in ("acronym", "acronym_compound")]
        tech_items = [(rec, v) for rec, v in all_items if not rec["is_normal_english"]]
        norm_items = [(rec, v) for rec, v in all_items if rec["is_normal_english"]]

        summary_by_config[cfg] = {
            "total_clips": n,
            "raw_exact_sentence_pct": _pct(sum(1 for _, v in all_items if v["raw_scores"]["exact_sentence"]), n),
            "raw_tech_term_pct": _pct(sum(1 for _, v in tech_items if v["raw_scores"]["term_hit"]), len(tech_items)),
            "raw_acronym_pct": _pct(
                sum(1 for _, v in acronym_items if v["raw_scores"]["acronym_exact"]),
                len(acronym_items),
            ),
            "raw_normal_english_pct": _pct(sum(1 for _, v in norm_items if v["raw_scores"]["term_hit"]), len(norm_items)),
            "post_recovery_tech_term_pct": _pct(
                sum(1 for _, v in tech_items if v["post_recovery_scores"]["term_hit"]),
                len(tech_items),
            ),
            "post_recovery_acronym_pct": _pct(
                sum(1 for _, v in acronym_items if v["post_recovery_scores"]["term_hit"]),
                len(acronym_items),
            ),
            "normal_english_hallucinations": sum(
                1 for _, v in norm_items if v["raw_scores"]["injected_tech_hallucination"]
            ),
            "retrieval_success_pct": _pct(
                sum(1 for _, v in all_items if v["phase2_and_retrieval"]["retrieval_success"]),
                n,
            ),
            "grounded_available_pct": _pct(
                sum(1 for _, v in all_items if v["phase2_and_retrieval"]["grounded_available"]),
                n,
            ),
            "avg_top_similarity": round(
                sum(v["phase2_and_retrieval"]["top_similarity"] for _, v in all_items) / n,
                4,
            ),
            "avg_stt_latency_ms": round(sum(v["stt_latency_ms"] for _, v in all_items) / n, 2),
            "avg_preprocess_ms": round(sum(v["preprocess_ms"] for _, v in all_items) / n, 2),
            "avg_total_latency_ms": round(sum(v["total_latency_ms"] for _, v in all_items) / n, 2),
            "columns_raw_term_pct": {
                "TCP": _col_term_pct("TCP", False),
                "SYN": _col_term_pct("SYN", False),
                "SYN Flood": _col_term_pct("SYN Flood", False),
                "DDoS": _col_term_pct("DDoS", False),
                "TCB": _col_term_pct("TCB", False),
                "Normal English": _col_term_pct("Normal English", False),
            },
            "columns_post_recovery_pct": {
                "TCP": _col_term_pct("TCP", True),
                "SYN": _col_term_pct("SYN", True),
                "SYN Flood": _col_term_pct("SYN Flood", True),
                "DDoS": _col_term_pct("DDoS", True),
                "TCB": _col_term_pct("TCB", True),
                "Normal English": _col_term_pct("Normal English", True),
            },
        }

    # Repeatability & Audio health aggregates
    det_count = sum(1 for c in clip_records if c["repeatability"]["deterministic"])
    diags = [c["audio_diagnostics"] for c in clip_records]
    normal_clips = [c for c in clip_records if c["is_normal_english"]]
    tech_clips = [c for c in clip_records if not c["is_normal_english"]]

    def _avg_diag(items: list[dict[str, Any]], key: str) -> float | None:
        vals = [c["audio_diagnostics"].get(key) for c in items if c["audio_diagnostics"].get(key) is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    audio_summary = {
        "total_recordings": len(clip_records),
        "codecs": sorted({d.get("codec") or "unknown" for d in diags}),
        "containers": sorted({d.get("container_format") or "unknown" for d in diags}),
        "native_sample_rates": sorted({d.get("native_sample_rate") for d in diags if d.get("native_sample_rate")}),
        "channel_counts": sorted({d.get("channels") for d in diags if d.get("channels")}),
        "avg_total_duration_s": _avg_diag(clip_records, "decoded_pcm_duration_s"),
        "avg_speech_duration_s": _avg_diag(clip_records, "speech_duration_s"),
        "avg_leading_silence_s": _avg_diag(clip_records, "leading_silence_s"),
        "avg_trailing_silence_s": _avg_diag(clip_records, "trailing_silence_s"),
        "avg_silence_pct": _avg_diag(clip_records, "silence_pct"),
        "avg_rms_energy": _avg_diag(clip_records, "rms_energy"),
        "avg_rms_dbfs": _avg_diag(clip_records, "rms_dbfs"),
        "avg_peak_amplitude": _avg_diag(clip_records, "peak_amplitude"),
        "avg_peak_dbfs": _avg_diag(clip_records, "peak_dbfs"),
        "avg_snr_db": _avg_diag(clip_records, "estimated_snr_db"),
        "max_clipping_fraction": max((d.get("clipping_fraction", 0.0) for d in diags), default=0.0),
        "normal_vs_technical_audio": {
            "normal_avg_rms_dbfs": _avg_diag(normal_clips, "rms_dbfs"),
            "technical_avg_rms_dbfs": _avg_diag(tech_clips, "rms_dbfs"),
            "normal_avg_snr_db": _avg_diag(normal_clips, "estimated_snr_db"),
            "technical_avg_snr_db": _avg_diag(tech_clips, "estimated_snr_db"),
            "normal_current_term_pct": summary_by_config["Current"]["raw_normal_english_pct"],
            "technical_current_term_pct": summary_by_config["Current"]["raw_tech_term_pct"],
        },
        "repeatability": {
            "deterministic_clips": det_count,
            "total_clips": len(clip_records),
            "repeatability_pct": _pct(det_count, len(clip_records)),
        },
    }

    report = {
        "manifest_meta": {
            "capture_mode": manifest.get("capture_mode"),
            "captured_at": manifest.get("captured_at"),
            "whisper_model": settings.VOICE_STT_MODEL,
            "compute_type": settings.VOICE_STT_COMPUTE_TYPE,
        },
        "audio_summary": audio_summary,
        "summary_by_config": summary_by_config,
        "recordings": clip_records,
    }

    results_json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_markdown_report(report, results_md_path)
    return report


def _fmt_pct(v: float | None) -> str:
    return f"{v:.1f}%" if v is not None else "n/a"


def _write_markdown_report(report: dict[str, Any], md_path: Path) -> None:
    audio = report["audio_summary"]
    cfg_sum = report["summary_by_config"]
    recs = report["recordings"]

    lines: list[str] = [
        "# Cognidocs Voice STT Diagnostic Report (Phase 2.1)",
        "",
        f"- **Capture Mode**: `{report['manifest_meta'].get('capture_mode')}`",
        f"- **Whisper Model**: `{report['manifest_meta'].get('whisper_model')}` (`{report['manifest_meta'].get('compute_type')}`, CPU)",
        f"- **Recordings Analyzed**: `{audio['total_recordings']}`",
        f"- **3x Repeatability (Deterministic)**: `{audio['repeatability']['deterministic_clips']}/{audio['repeatability']['total_clips']}` (`{audio['repeatability']['repeatability_pct']}%`)",
        "",
        "## Audio Signal Summary",
        "",
        f"- **Containers / Codecs**: `{audio['containers']}` / `{audio['codecs']}`",
        f"- **Native Sample Rates / Channels**: `{audio['native_sample_rates']}` Hz / `{audio['channel_counts']}` ch",
        f"- **Avg Total Duration**: `{audio['avg_total_duration_s']} s` (Speech: `{audio['avg_speech_duration_s']} s`, Silence: `{audio['avg_silence_pct']}%`)",
        f"- **Avg Leading / Trailing Silence**: `{audio['avg_leading_silence_s']} s` / `{audio['avg_trailing_silence_s']} s`",
        f"- **Avg RMS / Peak / Est. SNR**: `{audio['avg_rms_energy']}` (`{audio['avg_rms_dbfs']} dBFS`) / `{audio['avg_peak_amplitude']}` (`{audio['avg_peak_dbfs']} dBFS`) / `{audio['avg_snr_db']} dB`",
        f"- **Max Clipping Fraction**: `{audio['max_clipping_fraction']}`",
        "",
        "## Microphone vs Technical Recognition Diagnosis",
        "",
        f"- **Normal English (`E`, `F`)**: raw term accuracy `{audio['normal_vs_technical_audio']['normal_current_term_pct']}%`, avg RMS `{audio['normal_vs_technical_audio']['normal_avg_rms_dbfs']} dBFS`, SNR `{audio['normal_vs_technical_audio']['normal_avg_snr_db']} dB`",
        f"- **Technical Queries (`A–D`, `G–H`)**: raw term accuracy `{audio['normal_vs_technical_audio']['technical_current_term_pct']}%`, avg RMS `{audio['normal_vs_technical_audio']['technical_avg_rms_dbfs']} dBFS`, SNR `{audio['normal_vs_technical_audio']['technical_avg_snr_db']} dB`",
        "",
        "## Required Comparison Table (Raw STT Recognition & Latency)",
        "",
        "| Configuration | TCP | SYN | SYN Flood | DDoS | TCB | Normal English | Retrieval Success | Avg latency |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    key_rows = [
        "Current",
        "VAD",
        "Normalized",
        "VAD + normalized",
        "Whisper_Beam5",
        "Whisper_Temp0_NoCond",
        "Whisper_SoftVAD_035",
        "Whisper_NoVAD",
        "Whisper_Tuned",
        "Document prompt",
        "Document_Prompt_Tuned",
        "Mono_BestCh",
        "Resample_Float",
    ]
    for cfg in key_rows:
        if cfg not in cfg_sum:
            continue
        s = cfg_sum[cfg]
        c = s["columns_raw_term_pct"]
        lines.append(
            f"| {cfg} | {_fmt_pct(c['TCP'])} | {_fmt_pct(c['SYN'])} | {_fmt_pct(c['SYN Flood'])} | {_fmt_pct(c['DDoS'])} | {_fmt_pct(c['TCB'])} | {_fmt_pct(c['Normal English'])} | {_fmt_pct(s['retrieval_success_pct'])} | {s['avg_total_latency_ms']:.1f} ms |"
        )

    lines.extend([
        "",
        "## Comparison Table After Phase 2 Recovery",
        "",
        "| Configuration | Raw Tech Term | Post-Recovery Tech Term | Post-Recovery Acronym | Grounded Avail | Hallucinations (E/F) |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for cfg in key_rows:
        if cfg not in cfg_sum:
            continue
        s = cfg_sum[cfg]
        lines.append(
            f"| {cfg} | {_fmt_pct(s['raw_tech_term_pct'])} | {_fmt_pct(s['post_recovery_tech_term_pct'])} | {_fmt_pct(s['post_recovery_acronym_pct'])} | {_fmt_pct(s['grounded_available_pct'])} | {s['normal_english_hallucinations']} |"
        )

    lines.extend([
        "",
        "## Per-Recording Transcripts & Recovery Detail (`Current` vs `VAD + normalized` vs `Document prompt`)",
        "",
        "| Clip | Target | Dur (Speech) | SNR dB | Det? | Current Raw | Post-P2 Recovered | Retrieval |",
        "|---|---|---:|---:|---|---|---|---|",
    ])
    for rec in recs:
        d = rec["audio_diagnostics"]
        v_cur = rec["variants"]["Current"]
        p2 = v_cur["phase2_and_retrieval"]
        det_str = "YES" if rec["repeatability"]["deterministic"] else f"NO ({set(r['text'] for r in rec['repeatability']['runs'])})"
        ret_str = f"{'PASS' if p2['retrieval_success'] else 'FAIL'} ({p2['top_score']:.2f})"
        lines.append(
            f"| `{rec['clip_id']}` | {rec['expected_text']} | {d['decoded_pcm_duration_s']:.2f}s ({d['speech_duration_s']:.2f}s) | {d['estimated_snr_db']:.1f} | {det_str} | {v_cur['raw_text']!r} | {p2['effective_query']!r} ({p2['decision']}) | {ret_str} |"
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cognidocs Voice STT Diagnostic Benchmark (Phase 2.1)")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_RESULTS_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_RESULTS_MD)
    parser.add_argument("--probe", type=Path, default=None, help="Probe single audio file and print Section 2 diagnostics.")
    args = parser.parse_args()

    if args.probe:
        res = measure_audio_diagnostics(args.probe)
        print(json.dumps(res, indent=2))
        return

    report = run_diagnostic(args.manifest, args.out_json, args.out_md)
    print("\n=== DIAGNOSTIC COMPLETE ===")
    print(f"JSON: {args.out_json}")
    print(f"Markdown: {args.out_md}")
    print(json.dumps({
        "audio_summary": report["audio_summary"],
        "key_configs": {
            k: report["summary_by_config"][k]
            for k in ("Current", "VAD", "Normalized", "VAD + normalized", "Whisper_Tuned", "Document prompt")
            if k in report["summary_by_config"]
        },
    }, indent=2))


if __name__ == "__main__":
    main()
