"""LLM wrapper: Groq primary, Gemini secondary, disk cache keyed by prompt+system.

Env: GROQ_API_KEY, GEMINI_API_KEY, LLM_PROVIDER (groq|gemini forces one provider).
Cache files live in data/llm_cache/<sha256>.json and are read before any key check.
"""
import hashlib
import json
import os
import time

import requests

from src.config import LLM_CACHE_DIR, load_env

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-120b"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_MODEL = "gemini-flash-latest"
RETRY_STATUS = {429, 500, 502, 503, 504}
RETRIES = 3
TIMEOUT = 120


def _cache_key(prompt: str, system: str | None, json_mode: bool) -> str:
    # Provider-independent on purpose: the same prompt hits the cache whichever provider answered.
    payload = json.dumps({"system": system or "", "prompt": prompt, "json_mode": json_mode}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_path(key: str):
    return LLM_CACHE_DIR / f"{key}.json"


def _cache_read(key: str) -> str | None:
    path = _cache_path(key)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))["text"]


def _cache_write(key: str, text: str, provider: str) -> None:
    LLM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(key).write_text(json.dumps({"provider": provider, "text": text}, indent=2), encoding="utf-8")


def _post(url: str, headers: dict, body: dict) -> dict:
    """POST with retries on 429/5xx (exponential backoff). Returns the parsed JSON body."""
    for attempt in range(RETRIES + 1):
        resp = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
        if resp.status_code not in RETRY_STATUS or attempt == RETRIES:
            resp.raise_for_status()
            return resp.json()
        time.sleep(2 ** (attempt + 1))
    raise AssertionError("unreachable")


def _groq(prompt: str, system: str | None, json_mode: bool, key: str) -> str:
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    body = {"model": GROQ_MODEL, "messages": messages}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    data = _post(GROQ_URL, {"Authorization": f"Bearer {key}"}, body)
    return data["choices"][0]["message"]["content"]


def _gemini(prompt: str, system: str | None, json_mode: bool, key: str) -> str:
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if json_mode:
        body["generationConfig"] = {"responseMimeType": "application/json"}
    url = GEMINI_URL.format(model=GEMINI_MODEL)
    data = _post(url, {"x-goog-api-key": key}, body)
    return data["candidates"][0]["content"]["parts"][0]["text"]


PROVIDERS = {"groq": ("GROQ_API_KEY", _groq), "gemini": ("GEMINI_API_KEY", _gemini)}


def complete(prompt: str, system: str | None = None, json_mode: bool = False) -> str:
    """Return the LLM text for prompt. Cache hit returns without any key or network call."""
    load_env()
    key = _cache_key(prompt, system, json_mode)
    cached = _cache_read(key)
    if cached is not None:
        return cached

    forced = os.environ.get("LLM_PROVIDER", "").strip().lower()
    names = [forced] if forced else ["groq", "gemini"]
    errors = []
    tried = False
    for name in names:
        env_var, call = PROVIDERS[name]
        api_key = os.environ.get(env_var, "").strip()
        if not api_key:
            errors.append(f"{name}: {env_var} not set")
            continue
        tried = True
        try:
            text = call(prompt, system, json_mode, api_key)
        except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
            errors.append(f"{name}: {exc!r}")
            continue
        _cache_write(key, text, name)
        return text
    if not tried:
        raise RuntimeError(f"LLM cache miss and no API key available ({'; '.join(errors)})")
    raise RuntimeError(f"All LLM providers failed ({'; '.join(errors)})")
