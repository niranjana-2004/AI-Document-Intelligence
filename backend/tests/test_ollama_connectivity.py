import os
import sys
import time
from unittest.mock import patch, MagicMock
import requests
from app.core.database import Base
from fastapi.testclient import TestClient

from app.core.config import Settings, settings
from app.services.handwriting.ollama_client import (
    check_ollama_health,
    query_ollama,
    query_ollama_json,
    OllamaError,
    _health_cache
)
from app.main import app

client = TestClient(app)


def test_centralized_config_normalization():
    """Verify OLLAMA_BASE_URL is properly normalized and default avoids localhost IPv6 issues."""
    custom = Settings(OLLAMA_BASE_URL="http://192.168.1.50:11434/  ")
    assert custom.normalized_ollama_base_url == "http://192.168.1.50:11434"
    assert custom.ollama_generate_url == "http://192.168.1.50:11434/api/generate"
    assert custom.ollama_tags_url == "http://192.168.1.50:11434/api/tags"

    # Default check
    assert "127.0.0.1" in settings.normalized_ollama_base_url
    print("[PASS] test_centralized_config_normalization")


def test_health_check_connected():
    """Test health check when Ollama is reachable and model is present."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "models": [
            {"name": "llama3.2:latest", "model": "llama3.2:latest"},
            {"name": "mistral:latest", "model": "mistral:latest"}
        ]
    }

    with patch("requests.get", return_value=mock_resp):
        res = check_ollama_health(force_refresh=True)
        assert res["status"] == "connected"
        assert res["cached"] is False
        assert "llama3.2:latest" in res["available_models"]
        assert "ready" in res["message"].lower()
    print("[PASS] test_health_check_connected")


def test_health_check_model_missing():
    """Test health check when Ollama is reachable but required model is not installed."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "models": [
            {"name": "phi3:latest", "model": "phi3:latest"},
            {"name": "codellama:7b", "model": "codellama:7b"}
        ]
    }

    with patch("requests.get", return_value=mock_resp):
        res = check_ollama_health(force_refresh=True)
        assert res["status"] == "model_missing"
        assert "ollama pull" in res["message"].lower()
        assert res["required_model"] == settings.OLLAMA_MODEL
    print("[PASS] test_health_check_model_missing")


def test_health_check_connection_error():
    """Test health check when Ollama is unreachable (service down / wrong URL)."""
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Connection refused")):
        res = check_ollama_health(force_refresh=True)
        assert res["status"] == "unavailable"
        assert "ollama serve" in res["message"].lower()
        assert res["available_models"] == []
    print("[PASS] test_health_check_connection_error")


def test_health_check_timeout():
    """Test health check when connection times out."""
    with patch("requests.get", side_effect=requests.exceptions.Timeout("Request timed out")):
        res = check_ollama_health(force_refresh=True)
        assert res["status"] == "unavailable"
        assert "timed out" in res["message"].lower()
    print("[PASS] test_health_check_timeout")


def test_health_check_caching():
    """Test that health check caches responses within the TTL window unless force_refresh is True."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"models": [{"name": "llama3.2:latest"}]}

    with patch("requests.get", return_value=mock_resp) as mock_get:
        r1 = check_ollama_health(force_refresh=True)
        assert r1["cached"] is False
        assert mock_get.call_count == 1

        # Second call without force_refresh should hit the cache
        r2 = check_ollama_health(force_refresh=False)
        assert r2["cached"] is True
        assert mock_get.call_count == 1

        # Third call with force_refresh should bypass the cache
        r3 = check_ollama_health(force_refresh=True)
        assert r3["cached"] is False
        assert mock_get.call_count == 2
    print("[PASS] test_health_check_caching")


def test_query_ollama_model_not_found():
    """Test that query_ollama raises a clear OllamaError when model is missing (HTTP 404)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.text = '{"error":"model \'llama3.2\' not found"}'

    with patch("requests.post", return_value=mock_resp):
        caught = False
        try:
            query_ollama("Hello")
        except OllamaError as oe:
            caught = True
            assert "ollama pull" in str(oe).lower()
        assert caught, "Expected OllamaError was not raised"
    print("[PASS] test_query_ollama_model_not_found")


def test_query_ollama_connection_refused():
    """Test that query_ollama raises a clear OllamaError on connection error."""
    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("Connection refused")):
        caught = False
        try:
            query_ollama("Hello")
        except OllamaError as oe:
            caught = True
            assert "not running or unreachable" in str(oe).lower()
            assert settings.normalized_ollama_base_url in str(oe)
        assert caught, "Expected OllamaError was not raised"
    print("[PASS] test_query_ollama_connection_refused")


def test_query_ollama_timeout():
    """Test that query_ollama raises a clear OllamaError on timeout."""
    with patch("requests.post", side_effect=requests.exceptions.Timeout("Timed out")):
        caught = False
        try:
            query_ollama("Hello", timeout=10)
        except OllamaError as oe:
            caught = True
            assert "timed out" in str(oe).lower()
        assert caught, "Expected OllamaError was not raised"
    print("[PASS] test_query_ollama_timeout")


def test_fastapi_ai_health_endpoint():
    """Test GET /ai/health via FastAPI."""
    res = client.get("/ai/health?force_refresh=true")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "base_url" in data
    assert "required_model" in data
    print("[PASS] test_fastapi_ai_health_endpoint")


if __name__ == "__main__":
    print("\n--- Running Ollama Connectivity Test Suite ---")
    test_centralized_config_normalization()
    test_health_check_connected()
    test_health_check_model_missing()
    test_health_check_connection_error()
    test_health_check_timeout()
    test_health_check_caching()
    test_query_ollama_model_not_found()
    test_query_ollama_connection_refused()
    test_query_ollama_timeout()
    test_fastapi_ai_health_endpoint()
    print("\n=== ALL 10 CONNECTIVITY TESTS PASSED SUCCESSFULLY! ===\n")
