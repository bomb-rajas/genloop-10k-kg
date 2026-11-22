"""Offline tests for src/llm.py: Groq token limiter, 429 handling, Gemini fallback, cache bypass.

Time and HTTP are stubbed: FakeTime replaces llm.time so sleeps advance a fake clock; requests.post is stubbed.
"""
import pytest
import requests

from src import llm


class FakeResp:
    def __init__(self, status, body=None, headers=None, text=""):
        self.status_code = status
        self._body = body or {}
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class FakeTime:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


GROQ_OK = {"choices": [{"message": {"content": "groq-answer"}}]}
GEMINI_OK = {"candidates": [{"content": {"parts": [{"text": "gemini-answer"}]}}]}


@pytest.fixture
def clock(monkeypatch, tmp_path):
    fake = FakeTime()
    monkeypatch.setattr(llm, "time", fake)
    monkeypatch.setattr(llm, "LLM_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(llm, "load_env", lambda: None)
    monkeypatch.setattr(llm, "_gemini_next", 0.0)
    llm._GROQ_WINDOW.clear()
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    return fake


def test_limiter_sleeps_until_window_has_room(clock, monkeypatch):
    monkeypatch.setattr(llm, "GROQ_TPM_BUDGET", 6000)
    llm._groq_reserve(4000)
    llm._groq_reserve(1500)
    assert clock.sleeps == []
    llm._groq_reserve(1000)  # 6500 > 6000: wait until the t=0 entries leave the 60 s window
    assert clock.sleeps == [60.0]


def test_cache_hit_bypasses_limiter_and_network(clock, monkeypatch):
    key = llm._cache_key("hello", None, False)
    llm._cache_write(key, "cached answer", "groq")

    def boom(*a, **kw):
        raise AssertionError("network or limiter touched on cache hit")

    monkeypatch.setattr(llm, "_groq_reserve", boom)
    monkeypatch.setattr(llm.requests, "post", boom)
    assert llm.complete("hello") == "cached answer"
    assert len(llm._GROQ_WINDOW) == 0


def test_retry_wait_parses_hints_and_caps():
    assert llm._retry_wait(FakeResp(429, text="Rate limit. Please try again in 2.5s. Need more"), 0) == 2.5
    assert llm._retry_wait(FakeResp(429, text="try again in 800ms"), 0) == 0.8
    assert llm._retry_wait(FakeResp(429, headers={"retry-after": "7"}), 0) == 7.0
    assert llm._retry_wait(FakeResp(429, text="try again in 300s"), 0) == 60
    assert llm._retry_wait(FakeResp(429), 1) == 4


def test_groq_429_exhausted_then_gemini_fallback(clock, monkeypatch):
    monkeypatch.setattr(llm, "GROQ_TPM_BUDGET", 10**6)  # isolate the 429 path from the limiter
    calls = []

    def fake_post(url, **kw):
        calls.append((url, kw))
        if url == llm.GROQ_URL:
            return FakeResp(429, text="Please try again in 1s.")
        return FakeResp(200, GEMINI_OK)

    monkeypatch.setattr(llm.requests, "post", fake_post)
    assert llm.complete("prompt") == "gemini-answer"

    groq_calls = [c for c in calls if c[0] == llm.GROQ_URL]
    gemini_calls = [c for c in calls if c[0] != llm.GROQ_URL]
    assert len(groq_calls) == llm.GROQ_RETRIES + 1
    assert len(gemini_calls) == 1
    assert llm.GEMINI_MODEL in gemini_calls[0][0]
    assert groq_calls[0][1]["json"]["reasoning_effort"] == "low"
    assert clock.sleeps == [1.0] * llm.GROQ_RETRIES
    assert llm._cache_read(llm._cache_key("prompt", None, False)) == "gemini-answer"
