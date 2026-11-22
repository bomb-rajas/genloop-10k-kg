"""LLM wrapper: Groq primary, Gemini secondary, disk cache keyed by prompt+system.

Env: GROQ_API_KEY, GEMINI_API_KEY, LLM_PROVIDER (groq|gemini forces one provider), GROQ_TPM (Groq tokens/min, default 6000).
Cache files live in data/llm_cache/<sha256>.json and are read before any key check.
"""
import hashlib
import json
import os
import re
import threading
import time
from collections import deque

import requests

from src.config import LLM_CACHE_DIR, load_env

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-120b"
GROQ_TPM_BUDGET = int(os.environ.get("GROQ_TPM", "6000"))
GROQ_RETRIES = 4
REASONING_ALLOWANCE = 1500  # estimated output tokens per Groq call (reasoning + answer)
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_MODEL = "gemini-3.1-flash-lite"
GEMINI_RETRIES = 3
GEMINI_MIN_GAP = 6.0  # free tier is 10 requests/min; calls are serial
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_RETRY_WAIT = 60
WINDOW = 60.0
TIMEOUT = 120

_GROQ_LOCK = threading.Lock()
_GROQ_WINDOW: deque = deque()  # (monotonic time, estimated tokens) of Groq attempts in the last 60 s
_GEMINI_LOCK = threading.Lock()
_gemini_next = 0.0
_RETRY_IN = re.compile(r"try again in\s+(\d+(?:\.\d+)?)\s*(ms|s)\b", re.I)


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


def _retry_wait(resp, attempt: int) -> float:
    """Seconds to sleep after a retryable response: the server's hint if present, else exponential backoff; capped."""
    wait = None
    hint = resp.headers.get("retry-after")
    if hint:
        try:
            wait = float(hint)
        except ValueError:
            wait = None
    match = _RETRY_IN.search(resp.text or "")
    if wait is None and match:
        wait = float(match.group(1)) / (1000 if match.group(2).lower() == "ms" else 1)
    if wait is None:
        wait = 2 ** (attempt + 1)
    return min(wait, MAX_RETRY_WAIT)


def _post(url: str, headers: dict, body: dict, retries: int, reserve) -> dict:
    """POST; reserve() runs before every attempt; retries RETRY_STATUS up to `retries` times. Returns parsed JSON."""
    for attempt in range(retries + 1):
        reserve()
        resp = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
        if resp.status_code not in RETRY_STATUS or attempt == retries:
            resp.raise_for_status()
            return resp.json()
        time.sleep(_retry_wait(resp, attempt))
    raise AssertionError("unreachable")


def _groq_reserve(tokens: int) -> None:
    """Block until `tokens` fit in the sliding 60 s Groq budget, then record them."""
    with _GROQ_LOCK:
        while True:
            now = time.monotonic()
            while _GROQ_WINDOW and now - _GROQ_WINDOW[0][0] >= WINDOW:
                _GROQ_WINDOW.popleft()
            used = sum(n for _, n in _GROQ_WINDOW)
            # A single call larger than the whole budget is let through when the window is empty, else it would never run.
            if used + tokens <= GROQ_TPM_BUDGET or not _GROQ_WINDOW:
                _GROQ_WINDOW.append((now, tokens))
                return
            time.sleep(WINDOW - (now - _GROQ_WINDOW[0][0]))


def _groq(prompt: str, system: str | None, json_mode: bool, key: str) -> str:
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    body = {"model": GROQ_MODEL, "messages": messages, "reasoning_effort": "low"}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    tokens = (len(prompt) + len(system or "")) // 4 + REASONING_ALLOWANCE
    data = _post(GROQ_URL, {"Authorization": f"Bearer {key}"}, body, GROQ_RETRIES, lambda: _groq_reserve(tokens))
    return data["choices"][0]["message"]["content"]


def _gemini_reserve() -> None:
    """Keep attempts at least GEMINI_MIN_GAP apart. Called with _GEMINI_LOCK held."""
    global _gemini_next
    wait = _gemini_next - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _gemini_next = time.monotonic() + GEMINI_MIN_GAP


def _gemini(prompt: str, system: str | None, json_mode: bool, key: str) -> str:
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if json_mode:
        body["generationConfig"] = {"responseMimeType": "application/json"}
    url = GEMINI_URL.format(model=GEMINI_MODEL)
    with _GEMINI_LOCK:
        data = _post(url, {"x-goog-api-key": key}, body, GEMINI_RETRIES, _gemini_reserve)
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
