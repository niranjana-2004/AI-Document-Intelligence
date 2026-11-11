from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """
    Centralized configuration for Cognidocs.
    Loads settings from backend/.env and environment variables.
    """
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Core Security & App
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    FRONTEND_URL: str = "http://localhost:5173"

    # Layout Intelligence 4.0 Settings
    LAYOUT_GUIDED_OCR_ENABLED: bool = True

    # Ollama LLM Settings
    # Default to 127.0.0.1 to avoid Windows IPv6 localhost (::1) resolution issues.
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "llama3.2"
    OLLAMA_REQUEST_TIMEOUT: int = 300
    OLLAMA_HEALTH_CACHE_TTL: int = 20

    # Local Voice Assistant (STT + TTS) Settings
    VOICE_STT_MODEL: str = "base.en"
    VOICE_STT_COMPUTE_TYPE: str = "int8"
    VOICE_MAX_AUDIO_BYTES: int = 10 * 1024 * 1024  # 10 MB
    VOICE_MAX_DURATION_SECONDS: float = 90.0
    VOICE_TTS_MODEL: str = "en_US-lessac-medium"
    VOICE_TTS_MAX_CHARS: int = 4000
    VOICE_MODELS_DIR: str = str(BASE_DIR / "models" / "voice")

    @property
    def normalized_ollama_base_url(self) -> str:
        """Return Ollama base URL stripped of whitespace and trailing slashes."""
        url = (self.OLLAMA_BASE_URL or "http://127.0.0.1:11434").strip()
        return url.rstrip("/")

    @property
    def ollama_generate_url(self) -> str:
        """Full endpoint URL for Ollama generate API."""
        return f"{self.normalized_ollama_base_url}/api/generate"

    @property
    def ollama_tags_url(self) -> str:
        """Full endpoint URL for Ollama tags (installed models) API."""
        return f"{self.normalized_ollama_base_url}/api/tags"


settings = Settings()
