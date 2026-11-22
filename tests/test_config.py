from collections import Counter

import pytest
import requests

from src import llm
from src.config import load_companies, load_metrics

BANKS = {"JPM", "BAC", "C", "COF", "GS", "MS", "AXP"}
BANK_METRICS = {"Revenue", "NetIncome", "EPS", "TotalAssets", "TotalLiabilities", "Equity"}


def test_companies_count_and_sectors():
    companies = load_companies()
    assert len(companies) == 40
    assert len({c["ticker"] for c in companies}) == 40
    assert Counter(c["sector"] for c in companies) == {"Tech": 10, "Banks": 10, "Consumer": 10, "Healthcare": 10}


def test_companies_cik_and_bank_flags():
    companies = load_companies()
    for c in companies:
        assert isinstance(c["cik"], str) and len(c["cik"]) == 10 and c["cik"].isdigit(), c["ticker"]
    assert {c["ticker"] for c in companies if c["is_bank"]} == BANKS
    assert "COF" in {c["ticker"] for c in companies} and "WFC" not in {c["ticker"] for c in companies}


def test_metrics_bank_subset_and_counts():
    m = load_metrics()
    assert len(m["metrics"]) == 12
    bank = {x["name"] for x in m["metrics"] if x["applies_to"] == "all"}
    assert bank == BANK_METRICS
    assert {x["name"] for x in m["metrics"]} >= BANK_METRICS
    assert {x["name"] for x in m["derived"]} == {"NetMargin", "GrossMargin"}


def test_llm_cache_hit_needs_no_key(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "LLM_CACHE_DIR", tmp_path)
    monkeypatch.setattr(llm, "load_env", lambda: None)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    def no_network(*a, **k):
        raise AssertionError("network call on cache hit")

    monkeypatch.setattr(requests, "post", no_network)
    key = llm._cache_key("hello", "sys", False)
    llm._cache_write(key, "cached answer", "groq")
    assert llm.complete("hello", system="sys") == "cached answer"


def test_llm_cache_miss_without_key_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "LLM_CACHE_DIR", tmp_path)
    monkeypatch.setattr(llm, "load_env", lambda: None)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        llm.complete("never seen before")


def test_cache_key_differs_by_system_and_json_mode():
    assert llm._cache_key("p", None, False) == llm._cache_key("p", "", False)
    assert llm._cache_key("p", "s", False) != llm._cache_key("p", None, False)
    assert llm._cache_key("p", None, True) != llm._cache_key("p", None, False)
