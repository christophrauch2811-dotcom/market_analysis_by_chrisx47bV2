"""Tests fuer cache.py (Retry-Logik), news_filter.py, pinescript_generator.py."""
import time
import requests
import pytest

from tests.conftest import FakeResp


def test_retry_with_backoff_succeeds_after_failures():
    from market_analysis_by_chrisx47b.cache import retry_with_backoff
    calls = {"n": 0}

    @retry_with_backoff(max_attempts=3, base_delay=0.01)
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise requests.exceptions.Timeout("simuliert")
        return "ok"

    assert flaky() == "ok"
    assert calls["n"] == 3


def test_retry_with_backoff_reraises_after_exhaustion():
    from market_analysis_by_chrisx47b.cache import retry_with_backoff

    @retry_with_backoff(max_attempts=2, base_delay=0.01)
    def always_fails():
        raise requests.exceptions.ConnectionError("dauerhaft")

    with pytest.raises(requests.exceptions.ConnectionError):
        always_fails()


def test_ttl_cache_avoids_repeated_calls():
    from market_analysis_by_chrisx47b.cache import ttl_cache
    calls = {"n": 0}

    @ttl_cache(seconds=5)
    def slow(x):
        calls["n"] += 1
        return x * 2

    slow(1)
    slow(1)
    slow(1)
    assert calls["n"] == 1


def test_news_filter_rss_parsing():
    from market_analysis_by_chrisx47b.news_filter import fetch_rss
    fake_rss = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item><title>Bitcoin rallies</title><link>https://x/1</link>
<pubDate>Sat, 01 Aug 2026 08:00:00 GMT</pubDate><description>summary</description></item>
</channel></rss>"""

    import market_analysis_by_chrisx47b.news_filter as nf

    def fake_get(*a, **k):
        return FakeResp(None, content=fake_rss)

    orig = requests.get
    requests.get = fake_get
    try:
        items = fetch_rss.__wrapped__("https://fake/rss")
    finally:
        requests.get = orig
    assert len(items) == 1
    assert items[0]["title"] == "Bitcoin rallies"


def test_news_filter_relevance_and_impact():
    from market_analysis_by_chrisx47b.news_filter import score_relevance, classify_impact
    item = {"title": "SEC opens investigation into major exchange after hack", "summary": ""}
    assert classify_impact(item) == "high"
    assert score_relevance(item, ["bitcoin"]) == 0.0
    assert score_relevance({"title": "Bitcoin surges", "summary": ""}, ["bitcoin"]) == 1.0


def test_news_filter_deduplicates_similar_titles():
    from market_analysis_by_chrisx47b.news_filter import deduplicate
    items = [
        {"title": "Bitcoin surges past $70k as ETF inflows hit record high"},
        {"title": "Bitcoin surges past $70k as ETF inflows hit a record"},
        {"title": "Completely unrelated headline about cats"},
    ]
    result = deduplicate(items)
    assert len(result) == 2


def test_pinescript_indicator_generation_balanced_and_versioned():
    from market_analysis_by_chrisx47b.pinescript_generator import (
        generate_pine_indicator, SUPPORTED_INDICATOR_COMPONENTS,
    )
    for comp in SUPPORTED_INDICATOR_COMPONENTS:
        code = generate_pine_indicator(f"Test {comp}", [comp])
        assert code.startswith("//@version=6")
        assert code.count("(") == code.count(")")
        assert code.count("[") == code.count("]")


def test_pinescript_strategy_all_combinations_balanced():
    from market_analysis_by_chrisx47b.pinescript_generator import (
        generate_pine_strategy, SUPPORTED_ENTRY_METHODS,
    )
    for method in SUPPORTED_ENTRY_METHODS:
        for exit_m in ("percent", "atr"):
            for direction in ("long_only", "short_only", "both"):
                code = generate_pine_strategy("Test", entry_method=method,
                                               direction=direction, exit_method=exit_m)
                assert code.count("(") == code.count(")")
                assert "strategy(" in code


def test_pinescript_indicator_duplicate_components_get_unique_names():
    from market_analysis_by_chrisx47b.pinescript_generator import generate_pine_indicator
    code = generate_pine_indicator("Combo", ["ema", "ema", "rsi"])
    assert "emaVal1" in code and "emaVal2" in code
