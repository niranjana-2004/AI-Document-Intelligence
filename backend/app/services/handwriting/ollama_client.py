import json
import logging
import re
from typing import Any, Dict, Optional
import requests

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.2"


class OllamaError(RuntimeError):
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


def query_ollama(
    prompt: str,
    system_prompt: Optional[str] = None,
    format_json: bool = False,
    temperature: float = 0.2,
    timeout: int = 150
) -> str:
    """
    Send prompt to local Ollama LLM and return text response.
    """
    payload = {
        "model": DEFAULT_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature
        }
    }

    if system_prompt:
        payload["system"] = system_prompt

    if format_json:
        payload["format"] = "json"

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()
    except requests.exceptions.ConnectionError:
        raise OllamaError(
            "Ollama is not running or unreachable at http://localhost:11434. "
            "Please ensure the Ollama service is active."
        )
    except requests.exceptions.Timeout:
        raise OllamaError(
            f"Ollama request timed out after {timeout} seconds. Please try again with shorter content."
        )
    except Exception as e:
        raise OllamaError(f"Ollama request failed: {str(e)}")


def query_ollama_json(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.1,
    timeout: int = 150
) -> Any:
    """
    Send prompt to local Ollama LLM with format='json' and parse JSON response.
    """
    raw_response = query_ollama(
        prompt=prompt,
        system_prompt=system_prompt,
        format_json=True,
        temperature=temperature,
        timeout=timeout
    )
    return extract_json_from_text(raw_response)

