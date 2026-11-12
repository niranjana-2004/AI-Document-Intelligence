import json
import logging
import re
import time
from typing import Any, Dict, List, Optional
import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

# Maintain backward-compatible module aliases
OLLAMA_URL = settings.ollama_generate_url
DEFAULT_MODEL = settings.OLLAMA_MODEL

# In-memory health check cache
_health_cache: Dict[str, Any] = {
    "data": None,
    "expires_at": 0.0
}


class OllamaError(RuntimeError):
    """Custom exception for Ollama LLM errors."""
    pass


def extract_json_from_text(raw_text: str) -> Any:
    """
    Robustly extract and parse JSON from LLM output, handling markdown code fences,
    leading/trailing banter, and slight malformations.
    """
    cleaned = raw_text.strip()

    # Direct parse attempt
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Extract ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if match:
        code_block = match.group(1).strip()
        try:
            return json.loads(code_block)
        except Exception:
            cleaned = code_block

    # Search for first { or [ to matching end
    start_brace = cleaned.find("{")
    start_bracket = cleaned.find("[")

    start_idx = -1
    end_char = ""
    if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
        start_idx = start_brace
        end_char = "}"
    elif start_bracket != -1:
        start_idx = start_bracket
        end_char = "]"

    if start_idx != -1:
        end_idx = cleaned.rfind(end_char)
        if end_idx != -1 and end_idx > start_idx:
            sub = cleaned[start_idx:end_idx + 1]
            try:
                return json.loads(sub)
            except Exception:
                pass

    raise ValueError(f"Could not parse valid JSON from LLM output: {raw_text[:200]}...")


def check_ollama_health(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Check Ollama server reachability and configured model availability.
    Results are cached according to OLLAMA_HEALTH_CACHE_TTL unless force_refresh is True.
    """
    now = time.time()
    if not force_refresh and _health_cache["data"] is not None and now < _health_cache["expires_at"]:
        cached_result = dict(_health_cache["data"])
        cached_result["cached"] = True
        return cached_result

    target_model = settings.OLLAMA_MODEL.strip()
    target_base = target_model.split(":")[0].lower()
    base_url = settings.normalized_ollama_base_url

    start_time = time.perf_counter()
    try:
        resp = requests.get(settings.ollama_tags_url, timeout=3.5)
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)

        if resp.status_code == 200:
            data = resp.json()
            models_list = data.get("models", [])
            installed_names: List[str] = [m.get("name", "") for m in models_list if isinstance(m, dict)]

            # Check if required model is installed (matches exact name or base name without :tag)
            model_found = any(
                name.lower() == target_model.lower() or
                name.split(":")[0].lower() == target_base
                for name in installed_names
            )

            if model_found:
                result = {
                    "status": "connected",
                    "message": f"Ollama is running and model '{target_model}' is ready.",
                    "base_url": base_url,
                    "required_model": target_model,
                    "available_models": installed_names,
                    "response_time_ms": elapsed_ms,
                    "cached": False,
                    "timestamp": now
                }
            else:
                result = {
                    "status": "model_missing",
                    "message": f"Ollama is running at {base_url}, but required model '{target_model}' is not installed. Run 'ollama pull {target_model}'.",
                    "base_url": base_url,
                    "required_model": target_model,
                    "available_models": installed_names,
                    "response_time_ms": elapsed_ms,
                    "cached": False,
                    "timestamp": now
                }
        else:
            result = {
                "status": "unavailable",
                "message": f"Ollama returned HTTP {resp.status_code} at {base_url}.",
                "base_url": base_url,
                "required_model": target_model,
                "available_models": [],
                "response_time_ms": elapsed_ms,
                "cached": False,
                "timestamp": now
            }

    except requests.exceptions.ConnectionError:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
        result = {
            "status": "unavailable",
            "message": f"Ollama is not running or unreachable at {base_url}. Please ensure Ollama service is active (`ollama serve`).",
            "base_url": base_url,
            "required_model": target_model,
            "available_models": [],
            "response_time_ms": elapsed_ms,
            "cached": False,
            "timestamp": now
        }
    except requests.exceptions.Timeout:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
        result = {
            "status": "unavailable",
            "message": f"Connection to Ollama at {base_url} timed out.",
            "base_url": base_url,
            "required_model": target_model,
            "available_models": [],
            "response_time_ms": elapsed_ms,
            "cached": False,
            "timestamp": now
        }
    except Exception as e:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
        result = {
            "status": "unavailable",
            "message": f"Failed to connect to Ollama: {str(e)}",
            "base_url": base_url,
            "required_model": target_model,
            "available_models": [],
            "response_time_ms": elapsed_ms,
            "cached": False,
            "timestamp": now
        }

    # Cache result
    _health_cache["data"] = result
    _health_cache["expires_at"] = now + settings.OLLAMA_HEALTH_CACHE_TTL
    return result


def query_ollama(
    prompt: str,
    system_prompt: Optional[str] = None,
    format_json: bool = False,
    temperature: float = 0.2,
    timeout: Optional[int] = None,
    model: Optional[str] = None,
    num_ctx: Optional[int] = None,
    num_predict: Optional[int] = None,
) -> str:
    """
    Send prompt to local Ollama LLM and return text response.
    """
    active_model = model or settings.OLLAMA_MODEL
    active_timeout = timeout or settings.OLLAMA_REQUEST_TIMEOUT
    endpoint = settings.ollama_generate_url

    options: Dict[str, Any] = {
        "temperature": temperature,
        "num_ctx": int(num_ctx) if num_ctx is not None else 8192,
        "repeat_penalty": 1.1,
    }
    if num_predict is not None:
        options["num_predict"] = int(num_predict)

    payload = {
        "model": active_model,
        "prompt": prompt,
        "stream": False,
        "options": options,
    }

    if system_prompt:
        payload["system"] = system_prompt

    if format_json:
        payload["format"] = "json"

    try:
        resp = requests.post(endpoint, json=payload, timeout=active_timeout)
        if resp.status_code == 404:
            logger.error(f"Ollama model '{active_model}' not found at {endpoint}")
            raise OllamaError(
                f"Configured model '{active_model}' was not found on Ollama server ({settings.normalized_ollama_base_url}). "
                f"Please run 'ollama pull {active_model}' to download it."
            )
        if resp.status_code != 200:
            logger.error(f"Ollama returned {resp.status_code}: {resp.text}")
            raise OllamaError(f"Ollama error {resp.status_code}: {resp.text}")
        data = resp.json()
        return data.get("response", "").strip()
    except requests.exceptions.ConnectionError:
        raise OllamaError(
            f"Ollama is not running or unreachable at {settings.normalized_ollama_base_url}. "
            "Please ensure the Ollama service is active."
        )
    except requests.exceptions.Timeout:
        raise OllamaError(
            f"Ollama request timed out after {active_timeout} seconds at {settings.normalized_ollama_base_url}. "
            "Please try again with shorter content or check system load."
        )
    except OllamaError:
        raise
    except Exception as e:
        raise OllamaError(f"Ollama request failed: {str(e)}")


def query_ollama_json(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.1,
    timeout: Optional[int] = None,
    model: Optional[str] = None,
    num_ctx: Optional[int] = None,
    num_predict: Optional[int] = None,
) -> Any:
    """
    Send prompt to local Ollama LLM with format='json' and parse JSON response.
    """
    raw_response = query_ollama(
        prompt=prompt,
        system_prompt=system_prompt,
        format_json=True,
        temperature=temperature,
        timeout=timeout,
        model=model,
        num_ctx=num_ctx,
        num_predict=num_predict,
    )
    return extract_json_from_text(raw_response)
