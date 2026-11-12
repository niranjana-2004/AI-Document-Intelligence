import glob
import io
import json
import os
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.user import User
from app.services.embedding_services import generate_embedding
from app.services.tts_service import (
    TTSServiceError,
    prepare_text_for_speech,
    synthesize_speech_wav,
)
from app.services.voice_service import (
    VoiceTranscriptionError,
    transcribe_audio_bytes,
)


def _build_wav_bytes(samples: np.ndarray, sample_rate: int = 16000) -> bytes:
    pcm16 = np.clip(samples * 32767.0, -32768, 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16.tobytes())
    return buf.getvalue()


def _build_tone_wav_bytes(duration_sec: float = 1.0, freq_hz: float = 440.0, amp: float = 0.25) -> bytes:
    t = np.linspace(0, duration_sec, int(16000 * duration_sec), endpoint=False)
    return _build_wav_bytes(amp * np.sin(2.0 * np.pi * freq_hz * t))


def _piper_weights_available() -> bool:
    pdir = Path(settings.VOICE_MODELS_DIR) / "piper"
    onnx = pdir / f"{settings.VOICE_TTS_MODEL}.onnx"
    cfg = pdir / f"{settings.VOICE_TTS_MODEL}.onnx.json"
    return onnx.exists() and onnx.stat().st_size > 1_000_000 and cfg.exists() and cfg.stat().st_size > 100


class _FakeSegment:
    def __init__(self, text: str):
        self.text = text


class _FakeInfo:
    def __init__(self, language: str = "en"):
        self.language = language


class _FakeWhisperModel:
    def __init__(self, transcript_text: str = "What is a SYN flood?"):
        self.transcript_text = transcript_text

    def transcribe(self, audio_array, **kwargs):
        return [_FakeSegment(self.transcript_text)], _FakeInfo("en")


class TestVoiceAssistant(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=cls.engine
        )

        def override_get_db():
            db = cls.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        cls.prev_override = app.dependency_overrides.get(get_db)
        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        if cls.prev_override is not None:
            app.dependency_overrides[get_db] = cls.prev_override
        else:
            app.dependency_overrides.pop(get_db, None)

    def setUp(self):
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.TestingSessionLocal()
        self.user = User(
            id=1,
            email="voice_user@example.com",
            full_name="Voice Tester",
            password_hash=hash_password("Pass123!"),
            is_verified=True,
        )
        self.other_user = User(
            id=2,
            email="voice_other@example.com",
            full_name="Other User",
            password_hash=hash_password("Pass123!"),
            is_verified=True,
        )
        self.db.add_all([self.user, self.other_user])
        self.db.commit()
        token = create_access_token({"sub": str(self.user.id)})
        self.headers = {"Authorization": f"Bearer {token}"}

    def tearDown(self):
        self.db.close()

    # ------------------------------------------------------------------
    # 1. Authentication & Security Boundaries
    # ------------------------------------------------------------------
    def test_voice_endpoints_require_jwt_authentication(self):
        wav_bytes = _build_tone_wav_bytes()
        r_stt = self.client.post(
            "/voice/transcribe",
            files={"audio": ("query.wav", wav_bytes, "audio/wav")},
        )
        self.assertEqual(r_stt.status_code, 401)

        r_tts = self.client.post(
            "/voice/speak",
            json={"text": "Hello from Cognidocs."},
        )
        self.assertEqual(r_tts.status_code, 401)

    # ------------------------------------------------------------------
    # 2. Input Validation: Empty, Invalid MIME, Oversized, Silent Audio
    # ------------------------------------------------------------------
    def test_transcribe_rejects_empty_audio_file(self):
        res = self.client.post(
            "/voice/transcribe",
            files={"audio": ("empty.webm", b"", "audio/webm")},
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("empty", res.json()["detail"].lower())

    def test_transcribe_rejects_invalid_mime_type_and_extension(self):
        res = self.client.post(
            "/voice/transcribe",
            files={"audio": ("malicious.png", b"\x89PNG\r\n\x1a\nfake", "image/png")},
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 415)
        self.assertIn("unsupported", res.json()["detail"].lower())

    def test_transcribe_rejects_oversized_audio(self):
        oversized = b"0" * (settings.VOICE_MAX_AUDIO_BYTES + 10)
        res = self.client.post(
            "/voice/transcribe",
            files={"audio": ("huge.webm", oversized, "audio/webm")},
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 413)
        self.assertIn("maximum", res.json()["detail"].lower())

    def test_transcribe_rejects_silent_audio_and_too_short_clip(self):
        silent_wav = _build_wav_bytes(np.zeros(16000, dtype=np.float32))
        res_silent = self.client.post(
            "/voice/transcribe",
            files={"audio": ("silent.wav", silent_wav, "audio/wav")},
            headers=self.headers,
        )
        self.assertEqual(res_silent.status_code, 422)
        self.assertIn("no speech", res_silent.json()["detail"].lower())

        short_wav = _build_tone_wav_bytes(duration_sec=0.1)
        res_short = self.client.post(
            "/voice/transcribe",
            files={"audio": ("tiny.wav", short_wav, "audio/wav")},
            headers=self.headers,
        )
        self.assertEqual(res_short.status_code, 422)

    # ------------------------------------------------------------------
    # 3. Temp File Cleanup & Structured Response + Failure Handling
    # ------------------------------------------------------------------
    def test_valid_audio_transcription_and_temp_file_cleanup(self):
        pattern = os.path.join(tempfile.gettempdir(), "cognidocs_stt_*")
        before_files = set(glob.glob(pattern))
        wav_bytes = _build_tone_wav_bytes(duration_sec=1.2)

        with patch(
            "app.services.voice_service.get_whisper_model",
            return_value=_FakeWhisperModel("What is a SYN flood?"),
        ):
            res = self.client.post(
                "/voice/transcribe",
                files={"audio": ("mic_query.wav", wav_bytes, "audio/wav")},
                headers=self.headers,
            )

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["text"], "What is a SYN flood?")
        self.assertEqual(data["language"], "en")
        self.assertAlmostEqual(data["duration_seconds"], 1.2, places=1)
        self.assertIsNone(data["confidence"])
        self.assertEqual(data["engine"], "faster-whisper")
        self.assertIn("processing_time_ms", data)

        after_files = set(glob.glob(pattern))
        self.assertEqual(after_files, before_files)

    def test_temp_file_cleaned_up_even_on_stt_failure(self):
        pattern = os.path.join(tempfile.gettempdir(), "cognidocs_stt_*")
        before_files = set(glob.glob(pattern))
        wav_bytes = _build_tone_wav_bytes(duration_sec=0.8)

        with patch(
            "app.services.voice_service.get_whisper_model",
            side_effect=VoiceTranscriptionError("Local model failure"),
        ):
            res = self.client.post(
                "/voice/transcribe",
                files={"audio": ("broken.wav", wav_bytes, "audio/wav")},
                headers=self.headers,
            )

        self.assertEqual(res.status_code, 503)
        after_files = set(glob.glob(pattern))
        self.assertEqual(after_files, before_files)

    def test_webm_codec_mime_parameter_accepted(self):
        wav_bytes = _build_tone_wav_bytes(duration_sec=0.8)
        with patch(
            "app.services.voice_service.get_whisper_model",
            return_value=_FakeWhisperModel("Explain TCP handshake"),
        ):
            # Filename carries .webm while MIME includes codec parameters like Chrome MediaRecorder
            result = transcribe_audio_bytes(
                wav_bytes,
                filename="voice-query.webm",
                content_type="audio/webm;codecs=opus",
            )
        self.assertEqual(result["text"], "Explain TCP handshake")

    # ------------------------------------------------------------------
    # 4. TTS Formatting, Length Limits & Failure Handling
    # ------------------------------------------------------------------
    def test_prepare_text_for_speech_strips_citations_and_markdown(self):
        raw = (
            "### Overview\n"
            "**A SYN flood** exhausts server backlog queues [1, 2].\n"
            "- See [Source 1 | Document: Notes | File: notes.pdf | Page: 2] for details."
        )
        cleaned = prepare_text_for_speech(raw)
        self.assertNotIn("[1", cleaned)
        self.assertNotIn("[Source 1", cleaned)
        self.assertNotIn("###", cleaned)
        self.assertNotIn("**", cleaned)
        self.assertIn("A SYN flood exhausts server backlog queues.", cleaned)

    def test_speak_validates_text_and_length_limit(self):
        res_empty = self.client.post(
            "/voice/speak",
            json={"text": "   "},
            headers=self.headers,
        )
        self.assertEqual(res_empty.status_code, 422)

        too_long = "A" * (settings.VOICE_TTS_MAX_CHARS + 5)
        res_long = self.client.post(
            "/voice/speak",
            json={"text": too_long},
            headers=self.headers,
        )
        self.assertEqual(res_long.status_code, 422)

    def test_speak_returns_503_when_tts_engine_unavailable(self):
        with patch(
            "app.services.tts_service.get_piper_voice",
            side_effect=TTSServiceError("Piper missing"),
        ):
            res = self.client.post(
                "/voice/speak",
                json={"text": "Test speech response."},
                headers=self.headers,
            )
        self.assertEqual(res.status_code, 503)

    def test_tts_cancellation_before_synthesis(self):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(TTSServiceError):
            synthesize_speech_wav("Cancel me", cancel_event=cancel)

    # ------------------------------------------------------------------
    # 5. End-to-End Local Piper TTS + Faster-Whisper STT + Grounded QA
    # ------------------------------------------------------------------
    def test_voice_pipeline_connects_to_grounded_ask_ai_preserving_citations_and_isolation(self):
        text_p2 = (
            "A SYN flood is a denial-of-service attack that sends spoofed SYN packets "
            "so the half-open backlog queue fills up and blocks legitimate requests."
        )
        doc = Document(
            user_id=self.user.id,
            filename="network-security.pdf",
            document_type="PDF",
            file_path="uploads/network-security.pdf",
            extracted_text=text_p2,
            text_length=len(text_p2),
            processing_status="ready",
            processing_progress=100,
        )
        self.db.add(doc)
        self.db.flush()
        self.db.add(
            DocumentChunk(
                document_id=doc.id,
                chunk_index=0,
                page_number=2,
                content=text_p2,
                embedding=generate_embedding(text_p2),
            )
        )

        other_doc = Document(
            user_id=self.other_user.id,
            filename="secret-other.pdf",
            document_type="PDF",
            file_path="uploads/secret-other.pdf",
            extracted_text="Secret other tenant note about quantum rockets.",
            text_length=48,
            processing_status="ready",
            processing_progress=100,
        )
        self.db.add(other_doc)
        self.db.commit()

        # Real local Piper TTS -> real local faster-whisper STT smoke test when weights cached
        if _piper_weights_available():
            spoken_query = synthesize_speech_wav("What is a SYN flood?")
            self.assertEqual(spoken_query["media_type"], "audio/wav")
            self.assertGreater(len(spoken_query["audio_bytes"]), 1000)

            res_stt = self.client.post(
                "/voice/transcribe",
                files={"audio": ("question.wav", spoken_query["audio_bytes"], "audio/wav")},
                headers=self.headers,
            )
            self.assertEqual(res_stt.status_code, 200)
            transcribed_query = res_stt.json()["text"]
            self.assertTrue(len(transcribed_query) > 5)
        else:
            transcribed_query = "What is a SYN flood?"

        with patch(
            "app.services.question_service.generate_response",
            return_value="A SYN flood fills the server backlog queue with half-open connections [1].",
        ):
            res_ask = self.client.post(
                "/documents/ask",
                json={"query": transcribed_query, "document_ids": [doc.id]},
                headers=self.headers,
            )
        self.assertEqual(res_ask.status_code, 200)
        ask_data = res_ask.json()
        self.assertIn("backlog queue", ask_data["answer"])
        self.assertGreaterEqual(len(ask_data["sources"]), 1)
        self.assertEqual(ask_data["sources"][0]["page_number"], 2)

        # Ensure other user's document remains strictly inaccessible after voice flow
        res_iso = self.client.post(
            "/documents/ask",
            json={"query": transcribed_query, "document_ids": [other_doc.id]},
            headers=self.headers,
        )
        self.assertEqual(res_iso.status_code, 404)

        if _piper_weights_available():
            res_tts = self.client.post(
                "/voice/speak",
                json={"text": ask_data["answer"]},
                headers=self.headers,
            )
            self.assertEqual(res_tts.status_code, 200)
            self.assertEqual(res_tts.headers["content-type"], "audio/wav")
            self.assertGreater(len(res_tts.content), 44)

    def test_transcribe_uses_scoped_dynamic_document_initial_prompt_and_enforces_ownership(self):
        from app.models.document_chunk import DocumentChunk
        from app.services.embedding_services import generate_embedding
        from app.services.voice_terminology_service import (
            build_whisper_initial_prompt,
            clear_voice_terminology_cache,
        )

        clear_voice_terminology_cache()
        db = self.TestingSessionLocal()
        try:
            # Verify no-docs user produces no initial prompt
            self.assertIsNone(build_whisper_initial_prompt(db=db, user_id=self.user.id))

            chunk_text = (
                "TCP and SYN flood attacks target the Transmission Control Block (TCB) "
                "using spoofed SYN packets and RFC 5961 mitigations. SYN flood uses SYN packets over TCP."
            )
            net_doc = Document(
                user_id=self.user.id,
                filename="tcp_syn_flood.pdf",
                document_type="PDF",
                file_path="uploads/tcp_syn_flood.pdf",
                extracted_text=chunk_text,
                text_length=len(chunk_text),
                processing_status="ready",
                processing_progress=100,
            )
            db.add(net_doc)
            db.flush()
            db.add(
                DocumentChunk(
                    document_id=net_doc.id,
                    page_number=1,
                    chunk_index=0,
                    content=chunk_text,
                    embedding=generate_embedding(chunk_text),
                )
            )

            other_text = "ZXQ99 proprietary protocol uses ZXQ99 packets."
            other_doc = Document(
                user_id=self.other_user.id,
                filename="secret_xzq.pdf",
                document_type="PDF",
                file_path="uploads/secret_xzq.pdf",
                extracted_text=other_text,
                text_length=len(other_text),
                processing_status="ready",
                processing_progress=100,
            )
            db.add(other_doc)
            db.flush()
            db.add(
                DocumentChunk(
                    document_id=other_doc.id,
                    page_number=1,
                    chunk_index=0,
                    content=other_text,
                    embedding=generate_embedding(other_text),
                )
            )
            db.commit()

            prompt = build_whisper_initial_prompt(
                db=db,
                user_id=self.user.id,
                document_ids=[net_doc.id],
            )
            self.assertIsNotNone(prompt)
            self.assertLessEqual(len(prompt), 220)
            self.assertIn("SYN", prompt)
            self.assertIn("TCP", prompt)
            self.assertNotIn("ZXQ99", prompt)
            other_doc_id = other_doc.id
            net_doc_id = net_doc.id
        finally:
            db.close()

        captured_kwargs = {}

        class _CapturingFakeWhisper:
            def transcribe(self, audio_array, **kwargs):
                captured_kwargs.update(kwargs)
                return [_FakeSegment("What is SYN flood?")], _FakeInfo("en")

        wav_bytes = _build_tone_wav_bytes(duration_sec=0.8)
        with patch(
            "app.services.voice_service.get_whisper_model",
            return_value=_CapturingFakeWhisper(),
        ):
            res_ok = self.client.post(
                "/voice/transcribe",
                files={"audio": ("scoped.wav", wav_bytes, "audio/wav")},
                data={"document_ids": json.dumps([net_doc_id])},
                headers=self.headers,
            )
            self.assertEqual(res_ok.status_code, 200)
            self.assertEqual(res_ok.json()["text"], "What is SYN flood?")
            self.assertIn("initial_prompt", captured_kwargs)
            self.assertIn("SYN", captured_kwargs["initial_prompt"])
            self.assertNotIn("ZXQ99", captured_kwargs["initial_prompt"])

            # Cross-tenant document ID must be strictly rejected with 404
            res_forbidden = self.client.post(
                "/voice/transcribe",
                files={"audio": ("unowned.wav", wav_bytes, "audio/wav")},
                data={"document_ids": json.dumps([other_doc_id])},
                headers=self.headers,
            )
            self.assertEqual(res_forbidden.status_code, 404)

            # Malformed document_ids must fail cleanly with 422
            res_bad = self.client.post(
                "/voice/transcribe",
                files={"audio": ("bad.wav", wav_bytes, "audio/wav")},
                data={"document_ids": "not-an-id"},
                headers=self.headers,
            )
            self.assertEqual(res_bad.status_code, 422)


if __name__ == "__main__":
    unittest.main()

