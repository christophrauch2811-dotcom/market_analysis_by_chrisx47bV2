"""Tests fuer symbol_map.py und das compare_sources-Tool."""
import requests
import pytest

from tests.conftest import FakeResp


def test_to_source_symbol_all_sources():
    from market_analysis_by_chrisx47b.symbol_map import to_source_symbol
    expected = {
        "crypto": "BTC_USDT", "binance": "BTCUSDT", "bybit": "BTCUSDT",
        "kucoin": "BTC-USDT", "kraken": "XBTUSDT", "bitfinex": "tBTCUST",
        "coingecko": "bitcoin", "yahoo": "BTC-USD",
    }
    for source, expected_symbol in expected.items():
        assert to_source_symbol("BTC/USDT", source) == expected_symbol


def test_to_source_symbol_unknown_coingecko_coin_raises():
    from market_analysis_by_chrisx47b.symbol_map import to_source_symbol
    with pytest.raises(ValueError, match="CoinGecko-ID"):
        to_source_symbol("NOTAREALCOIN/USDT", "coingecko")


def test_normalize_symbol_roundtrip():
    from market_analysis_by_chrisx47b.symbol_map import normalize_symbol, to_source_symbol
    cases = [
        ("crypto", "BTC_USDT"), ("binance", "BTCUSDT"), ("kucoin", "BTC-USDT"),
        ("kraken", "XBTUSDT"), ("bitfinex", "tBTCUST"), ("yahoo", "BTC-USD"),
    ]
    for source, symbol in cases:
        canonical = normalize_symbol(symbol, source)
        assert to_source_symbol(canonical, source) == symbol


def test_map_to_sources_skips_unmappable_without_crashing():
    from market_analysis_by_chrisx47b.symbol_map import map_to_sources
    result = map_to_sources("NOTAREALCOIN/USDT", ["binance", "coingecko"])
    sources_returned = [r["source"] for r in result]
    assert "binance" in sources_returned
    assert "coingecko" not in sources_returned  # kein Mapping moeglich -> ausgelassen


def test_compare_sources_finds_cheapest_and_spread(monkeypatch):
    from market_analysis_by_chrisx47b.sources import binance, bybit, kraken

    def fake_get(url, params=None, timeout=None, headers=None):
        if "binance.com" in url and "ticker" in url:
            return FakeResp({"symbol": "BTCUSDT", "lastPrice": "63000.50"})
        if "bybit.com" in url and "tickers" in url:
            return FakeResp({"retCode": 0, "retMsg": "OK", "result": {"list": [{"lastPrice": "63150.00"}]}})
        if "kraken.com" in url and "Ticker" in url:
            return FakeResp({"error": [], "result": {"XXBTZUSDT": {"c": ["62980.25", "0.1"]}}})
        raise Exception("unerwartete URL: " + url)

    monkeypatch.setattr(requests, "get", fake_get)
    binance.get_ticker.cache_clear()
    bybit.get_ticker.cache_clear()
    kraken.get_ticker.cache_clear()

    from market_analysis_by_chrisx47b import server
    tool = server.mcp._tool_manager._tools["compare_sources"]
    result = tool.fn(canonical_symbol="BTC/USDT", sources=["binance", "bybit", "kraken"])

    assert result["results"]["kraken"]["symbol"] == "XBTUSDT"
    assert result["spread"]["cheapest_source"] == "kraken"
    assert result["spread"]["most_expensive_source"] == "bybit"
    assert result["spread"]["spread_abs"] > 0
