"""
Standalone non-production browser audio capture utility for Cognidocs Phase 2.1 STT Diagnostic.

Uses the exact browser capture pipeline from frontend/src/pages/AskAI.jsx and voiceUtils.js:
  navigator.mediaDevices.getUserMedia({ audio: true })
  -> MIME candidate negotiation (audio/webm;codecs=opus preferred)
  -> new MediaRecorder(stream, recorderOptions).start(250)

Saves recorded clips directly to backend/benchmarks/voice_stt_diagnostic_clips/
and populates backend/benchmarks/voice_stt_diagnostic_manifest.json.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.services.voice_service import decode_audio_to_16k_mono, get_whisper_model
from benchmarks.run_voice_stt_diagnostic import (
    BENCHMARKS_DIR,
    CLIPS_DIR,
    DEFAULT_MANIFEST_PATH,
    DIAGNOSTIC_PROMPTS,
    measure_audio_diagnostics,
    run_whisper_transcribe,
)

PORT = 8765
REPS_PER_QUERY = 3
_STATE_LOCK = threading.Lock()


def build_slots() -> list[dict[str, Any]]:
    slots = []
    for p in DIAGNOSTIC_PROMPTS:
        for rep in range(1, REPS_PER_QUERY + 1):
            slots.append({
                "clip_id": f"{p['group'].lower()}_{rep}",
                "group": p["group"],
                "rep": rep,
                "expected_text": p["text"],
                "category": p["category"],
            })
    return slots


SLOTS = build_slots()
SLOT_MAP = {s["clip_id"]: s for s in SLOTS}


def _load_manifest() -> dict[str, Any]:
    if DEFAULT_MANIFEST_PATH.exists():
        try:
            data = json.loads(DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("recordings"), list):
                return data
        except Exception:
            pass
    return {
        "capture_mode": "real_browser_microphone",
        "captured_at": None,
        "target_reps_per_prompt": REPS_PER_QUERY,
        "prompts": [{"group": p["group"], "text": p["text"], "category": p["category"]} for p in DIAGNOSTIC_PROMPTS],
        "recordings": [],
    }


def _save_manifest(data: dict[str, Any]) -> None:
    data["captured_at"] = datetime.now(timezone.utc).isoformat()
    DEFAULT_MANIFEST_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _extension_for_mime(mime_type: str) -> str:
    base = (mime_type or "").split(";")[0].strip().lower()
    if base in ("audio/ogg", "application/ogg"):
        return ".ogg"
    if base in ("audio/mp4", "audio/m4a", "audio/x-m4a"):
        return ".mp4"
    if base in ("audio/wav", "audio/x-wav", "audio/wave"):
        return ".wav"
    if base in ("audio/mpeg", "audio/mp3"):
        return ".mp3"
    return ".webm"


HTML_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Cognidocs STT Diagnostic Recorder (Phase 2.1)</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b1020;
      --panel: #131a30;
      --panel2: #192340;
      --border: #2a3761;
      --text: #eef2ff;
      --muted: #9aa7cc;
      --accent: #7c5cff;
      --accent-soft: rgba(124,92,255,0.16);
      --ok: #22c55e;
      --danger: #ef4444;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background: var(--bg); color: var(--text); min-height: 100vh;
      display: flex; flex-direction: column; align-items: center; padding: 24px 16px;
    }
    .wrap { width: 100%; max-width: 820px; display: flex; flex-direction: column; gap: 16px; }
    .card {
      background: var(--panel); border: 1px solid var(--border);
      border-radius: 14px; padding: 18px 20px;
    }
    .header { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
    h1 { font-size: 18px; margin: 0; }
    .sub { color: var(--muted); font-size: 13px; margin: 4px 0 0; }
    .pill {
      padding: 5px 11px; border-radius: 999px; font-size: 12.5px; font-weight: 700;
      background: var(--accent-soft); border: 1px solid var(--accent); color: #d8ceff;
    }
    .pill.done { background: rgba(34,197,94,0.16); border-color: var(--ok); color: #bbf7d0; }
    .prompt-box {
      background: var(--panel2); border: 1px solid var(--border);
      border-radius: 12px; padding: 20px; text-align: center;
    }
    .slot-meta { font-size: 12.5px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }
    .phrase { font-size: 28px; font-weight: 700; margin: 10px 0; color: #ffffff; }
    .guidance { font-size: 13px; color: var(--muted); margin: 0; }
    .controls { display: flex; align-items: center; justify-content: center; gap: 12px; margin-top: 18px; flex-wrap: wrap; }
    button {
      border: 1px solid var(--border); border-radius: 10px; padding: 10px 18px;
      font-size: 14px; font-weight: 600; cursor: pointer; font-family: inherit;
      background: var(--panel); color: var(--text); transition: 0.15s ease;
    }
    button:hover:not(:disabled) { border-color: var(--accent); }
    button:disabled { opacity: 0.45; cursor: not-allowed; }
    .btn-rec { background: var(--accent); border-color: var(--accent); color: #fff; min-width: 170px; }
    .btn-rec.recording { background: var(--danger); border-color: var(--danger); }
    .stats { font-family: ui-monospace, Consolas, monospace; font-size: 12.5px; color: #cbd5e1; white-space: pre-wrap; margin: 0; }
    .grid {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px;
    }
    .slot-btn {
      text-align: left; padding: 8px 10px; font-size: 12px; border-radius: 8px;
      background: var(--panel2); border: 1px solid var(--border); display: flex; flex-direction: column; gap: 3px;
    }
    .slot-btn.active { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }
    .slot-btn.recorded { border-color: rgba(34,197,94,0.6); }
    .slot-top { display: flex; justify-content: space-between; font-weight: 700; }
    .tag-ok { color: #4ade80; }
    .tag-todo { color: var(--muted); }
    .err { color: #fca5a5; font-size: 13px; min-height: 18px; margin-top: 8px; text-align: center; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <div class="header">
        <div>
          <h1>Cognidocs Phase 2.1 — Real Microphone Diagnostic Capture</h1>
          <p class="sub">Non-production test utility using Cognidocs' exact browser <code>MediaRecorder</code> pipeline.</p>
        </div>
        <span id="progressPill" class="pill">0 / 24 recorded</span>
      </div>
    </div>

    <div class="card prompt-box">
      <div id="slotMeta" class="slot-meta">Loading...</div>
      <div id="phraseText" class="phrase">...</div>
      <p class="guidance">Speak naturally at your normal pace and volume. Press <strong>Space</strong> or click Start/Stop.</p>
      <div class="controls">
        <button id="prevBtn" type="button">Previous</button>
        <button id="recBtn" type="button" class="btn-rec">Start Recording</button>
        <button id="nextBtn" type="button">Next</button>
      </div>
      <div id="statusErr" class="err"></div>
    </div>

    <div class="card">
      <div style="font-size:13px;font-weight:700;margin-bottom:8px;">Latest Clip Measurement &amp; Baseline STT</div>
      <pre id="diagOut" class="stats">Record a clip to view container, VAD, RMS, peak, SNR, and raw baseline STT transcript.</pre>
    </div>

    <div class="card">
      <div style="font-size:13px;font-weight:700;margin-bottom:10px;">All 24 Diagnostic Clips (Click any slot to record or re-record)</div>
      <div id="slotGrid" class="grid"></div>
    </div>
  </div>

  <script>
    const MIME_CANDIDATES = [
      { mimeType: 'audio/webm;codecs=opus', extension: '.webm' },
      { mimeType: 'audio/webm', extension: '.webm' },
      { mimeType: 'audio/ogg;codecs=opus', extension: '.ogg' },
      { mimeType: 'audio/ogg', extension: '.ogg' },
      { mimeType: 'audio/mp4', extension: '.mp4' },
      { mimeType: 'audio/wav', extension: '.wav' },
    ];
    function getSupportedMime() {
      if (typeof MediaRecorder === 'undefined' || typeof MediaRecorder.isTypeSupported !== 'function') {
        return { mimeType: '', extension: '.webm' };
      }
      for (const c of MIME_CANDIDATES) {
        try { if (MediaRecorder.isTypeSupported(c.mimeType)) return c; } catch {}
      }
      return { mimeType: '', extension: '.webm' };
    }

    let slots = [];
    let recordedMap = {};
    let activeIdx = 0;
    let isRecording = false;
    let isUploading = false;
    let activeStream = null;
    let mediaRecorder = null;
    let chunks = [];
    let recStartTs = 0;
    let recTimer = null;

    const elProgress = document.getElementById('progressPill');
    const elSlotMeta = document.getElementById('slotMeta');
    const elPhrase = document.getElementById('phraseText');
    const elRecBtn = document.getElementById('recBtn');
    const elPrev = document.getElementById('prevBtn');
    const elNext = document.getElementById('nextBtn');
    const elErr = document.getElementById('statusErr');
    const elDiag = document.getElementById('diagOut');
    const elGrid = document.getElementById('slotGrid');

    async function loadStatus(jumpToFirstUnrecorded = false) {
      const res = await fetch('/api/status');
      const data = await res.json();
      slots = data.slots;
      recordedMap = {};
      for (const r of data.recordings) recordedMap[r.clip_id] = r;
      if (jumpToFirstUnrecorded) {
        const firstTodo = slots.findIndex(s => !recordedMap[s.clip_id]);
        if (firstTodo >= 0) activeIdx = firstTodo;
      }
      render();
    }

    function render() {
      const doneCount = slots.filter(s => Boolean(recordedMap[s.clip_id])).length;
      elProgress.textContent = `${doneCount} / ${slots.length} recorded`;
      elProgress.className = doneCount >= slots.length ? 'pill done' : 'pill';

      const cur = slots[activeIdx] || {};
      const existing = recordedMap[cur.clip_id];
      elSlotMeta.textContent = `Prompt ${cur.group} · Take ${cur.rep} of 3 (${cur.clip_id})${existing ? ' · Recorded (click Start to overwrite)' : ''}`;
      elPhrase.textContent = `“${cur.expected_text || ''}”`;

      elPrev.disabled = isRecording || isUploading || activeIdx <= 0;
      elNext.disabled = isRecording || isUploading || activeIdx >= slots.length - 1;
      elRecBtn.disabled = isUploading;

      if (existing && existing.last_summary && !isRecording && !isUploading) {
        elDiag.textContent = existing.last_summary;
      }

      elGrid.innerHTML = '';
      slots.forEach((s, idx) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        const rec = recordedMap[s.clip_id];
        btn.className = `slot-btn ${idx === activeIdx ? 'active' : ''} ${rec ? 'recorded' : ''}`;
        btn.disabled = isRecording || isUploading;
        btn.innerHTML = `<div class="slot-top"><span>${s.group}${s.rep} (${s.clip_id})</span><span class="${rec ? 'tag-ok' : 'tag-todo'}">${rec ? 'SAVED' : 'TODO'}</span></div><div style="color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${s.expected_text}</div>`;
        btn.onclick = () => { activeIdx = idx; elErr.textContent = ''; render(); };
        elGrid.appendChild(btn);
      });
    }

    async function startRecording() {
      elErr.textContent = '';
      const slot = slots[activeIdx];
      if (!slot) return;
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        activeStream = stream;
        chunks = [];
        const track = stream.getAudioTracks()[0];
        const trackSettings = track?.getSettings ? track.getSettings() : {};
        const trackLabel = track?.label || 'unknown';
        let audioCtxSampleRate = null;
        try {
          const AC = window.AudioContext || window.webkitAudioContext;
          if (AC) { const ctx = new AC(); audioCtxSampleRate = ctx.sampleRate; ctx.close().catch(() => {}); }
        } catch {}

        const { mimeType } = getSupportedMime();
        const opts = mimeType ? { mimeType } : undefined;
        const recorder = new MediaRecorder(stream, opts);
        mediaRecorder = recorder;

        recorder.ondataavailable = (ev) => { if (ev.data && ev.data.size > 0) chunks.push(ev.data); };
        recorder.onerror = () => {
          cleanupStream();
          isRecording = false;
          elRecBtn.textContent = 'Start Recording';
          elRecBtn.classList.remove('recording');
          elErr.textContent = 'MediaRecorder failed unexpectedly. Try again.';
          render();
        };
        recorder.onstop = async () => {
          const actualMime = recorder.mimeType || mimeType || 'audio/webm';
          const elapsedMs = Date.now() - recStartTs;
          cleanupStream();
          const blob = new Blob(chunks, { type: actualMime });
          chunks = [];
          isRecording = false;
          elRecBtn.textContent = 'Start Recording';
          elRecBtn.classList.remove('recording');

          if (!blob || blob.size === 0) {
            elErr.textContent = 'Recorded blob was empty. Please record again.';
            render();
            return;
          }

          isUploading = true;
          elDiag.textContent = `Saving & measuring ${slot.clip_id}...`;
          render();
          try {
            const meta = {
              clip_id: slot.clip_id,
              actual_mime: actualMime,
              client_elapsed_ms: elapsedMs,
              track_label: trackLabel,
              track_settings: trackSettings,
              audio_context_sample_rate: audioCtxSampleRate,
            };
            const saveRes = await fetch('/api/save', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/octet-stream',
                'X-Capture-Meta': encodeURIComponent(JSON.stringify(meta)),
              },
              body: blob,
            });
            const saved = await saveRes.json();
            if (!saveRes.ok) throw new Error(saved.error || 'Save failed');
            elDiag.textContent = saved.summary;
            await loadStatus(false);
            // Auto-advance to next unrecorded slot cleanly
            const nextTodo = slots.findIndex((s, i) => i > activeIdx && !recordedMap[s.clip_id]);
            if (nextTodo >= 0) {
              activeIdx = nextTodo;
            } else {
              const anyTodo = slots.findIndex(s => !recordedMap[s.clip_id]);
              if (anyTodo >= 0) activeIdx = anyTodo;
            }
          } catch (e) {
            elErr.textContent = e.message || 'Upload failed';
          } finally {
            isUploading = false;
            render();
          }
        };

        recStartTs = Date.now();
        recorder.start(250);
        isRecording = true;
        elRecBtn.classList.add('recording');
        elRecBtn.textContent = 'Stop Recording (0s)';
        recTimer = setInterval(() => {
          const sec = Math.floor((Date.now() - recStartTs) / 1000);
          elRecBtn.textContent = `Stop Recording (${sec}s)`;
        }, 250);
        render();
      } catch (err) {
        cleanupStream();
        isRecording = false;
        elErr.textContent = `Microphone error: ${err?.name || ''} ${err?.message || err}`;
        render();
      }
    }

    function stopRecording() {
      if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
      }
    }

    function cleanupStream() {
      if (recTimer) { clearInterval(recTimer); recTimer = null; }
      if (activeStream) {
        activeStream.getTracks().forEach(t => { try { t.stop(); } catch {} });
        activeStream = null;
      }
      mediaRecorder = null;
    }

    elRecBtn.onclick = () => { if (isRecording) stopRecording(); else startRecording(); };
    elPrev.onclick = () => { if (activeIdx > 0) { activeIdx--; elErr.textContent = ''; render(); } };
    elNext.onclick = () => { if (activeIdx < slots.length - 1) { activeIdx++; elErr.textContent = ''; render(); } };
    window.addEventListener('keydown', (e) => {
      if (e.code === 'Space' && !e.repeat) {
        e.preventDefault();
        if (!isUploading) { if (isRecording) stopRecording(); else startRecording(); }
      }
    });

    loadStatus(true);
  </script>
</body>
</html>
"""


class CaptureHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        # Quiet clean console logging
        pass

    def _send_json(self, status: int, payload: Any) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            body = HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/status":
            with _STATE_LOCK:
                manifest = _load_manifest()
            self._send_json(200, {
                "slots": SLOTS,
                "recordings": manifest.get("recordings", []),
            })
            return

        self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/save":
            self._send_json(404, {"error": "Not found"})
            return

        meta_header = self.headers.get("X-Capture-Meta")
        if not meta_header:
            self._send_json(400, {"error": "Missing capture metadata"})
            return
        meta = json.loads(urllib.parse.unquote(meta_header))
        clip_id = meta.get("clip_id", "")
        slot = SLOT_MAP.get(clip_id)
        if not slot:
            self._send_json(400, {"error": f"Unknown clip_id: {clip_id}"})
            return

        length = int(self.headers.get("Content-Length") or 0)
        audio_bytes = self.rfile.read(length)
        if not audio_bytes:
            self._send_json(400, {"error": "Empty audio payload"})
            return

        CLIPS_DIR.mkdir(parents=True, exist_ok=True)
        ext = _extension_for_mime(meta.get("actual_mime", ""))
        out_path = CLIPS_DIR / f"{clip_id}{ext}"
        out_path.write_bytes(audio_bytes)

        diag = measure_audio_diagnostics(out_path, frontend_meta=meta)
        pcm = decode_audio_to_16k_mono(str(out_path))
        model = get_whisper_model()
        stt = run_whisper_transcribe(model, pcm, language="en", beam_size=2, vad_filter=True)

        summary = (
            f"Clip: {clip_id} ({slot['expected_text']})\n"
            f"File: {out_path.name} ({len(audio_bytes)} bytes) | Codec: {diag.get('codec')} | "
            f"Native Rate: {diag.get('native_sample_rate')} Hz | Ch: {diag.get('channels')}\n"
            f"Total dur: {diag['decoded_pcm_duration_s']:.2f}s | Speech: {diag['speech_duration_s']:.2f}s | "
            f"Lead/Trail silence: {diag['leading_silence_s']:.2f}s / {diag['trailing_silence_s']:.2f}s ({diag['silence_pct']:.1f}% silence)\n"
            f"RMS: {diag['rms_energy']} ({diag['rms_dbfs']} dBFS) | Peak: {diag['peak_amplitude']} ({diag['peak_dbfs']} dBFS) | SNR: {diag['estimated_snr_db']} dB\n"
            f"Mic Track: {meta.get('track_label')} | Settings: {json.dumps(meta.get('track_settings', {}))}\n"
            f"Baseline STT ({stt['latency_ms']} ms): {stt['text']!r}"
        )

        rel_file = str(out_path.relative_to(BENCHMARKS_DIR)).replace("\\", "/")
        rec_entry = {
            "clip_id": clip_id,
            "group": slot["group"],
            "rep": slot["rep"],
            "expected_text": slot["expected_text"],
            "category": slot["category"],
            "file_path": rel_file,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "frontend_meta": meta,
            "initial_measurements": diag,
            "baseline_stt_preview": stt["text"],
            "last_summary": summary,
        }

        with _STATE_LOCK:
            manifest = _load_manifest()
            recs = [r for r in manifest.get("recordings", []) if r.get("clip_id") != clip_id]
            recs.append(rec_entry)
            order = {s["clip_id"]: i for i, s in enumerate(SLOTS)}
            recs.sort(key=lambda r: order.get(r["clip_id"], 999))
            manifest["recordings"] = recs
            _save_manifest(manifest)

        print(f"[SAVED] {clip_id} -> {rel_file} | dur={diag['decoded_pcm_duration_s']:.2f}s snr={diag['estimated_snr_db']}dB stt={stt['text']!r}")
        self._send_json(200, {"ok": True, "summary": summary, "total_saved": len(recs)})


def main() -> None:
    print(f"Pre-loading Whisper ({settings.VOICE_STT_MODEL}) for live capture diagnostics...")
    get_whisper_model()
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), CaptureHandler)
    print(f"Cognidocs STT Diagnostic Recorder ready at: http://localhost:{PORT}/")
    print("Waiting for real browser microphone captures (24 slots: A1..H3)...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCapture server stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
