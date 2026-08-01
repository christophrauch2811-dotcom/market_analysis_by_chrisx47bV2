"""Tests fuer sources/*.py -- alle mit gemockten Antworten im jeweils echten
API-Format (verifiziert gegen die offizielle Doku, siehe README/CLAUDE.md).
Kein Netzwerkzugriff, kein API-Key noetig.
"""
import requests
import pytest

from tests.conftest import FakeResp

NOW_MS = 1785600000000
NOW_S = NOW_MS // 1000


def test_crypto_com_candlestick(monkeypatch):
    from market_analysis_by_chrisx47b.sources import crypto_com
    crypto_com.get_candlestick.cache_clear()

    data = {"result": {"data": [
        {"o": "100", "h": "101", "l": "99", "c": "100.5", "v": "10", "t": NOW_MS - i * 3600000}
        for i in range(5)
    ]}}
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResp(data))
    df = crypto_com.get_candlestick("BTC_USDT", "1h", 5)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert len(df) == 5


def test_crypto_com_ticker_endpoint_is_plural(monkeypatch):
    """Regressionstest fuer den gefundenen Bug: Endpunkt muss 'get-tickers'
    (Plural) sein, nicht 'get-ticker'."""
    from market_analysis_by_chrisx47b.sources import crypto_com
    crypto_com.get_ticker.cache_clear()

    captured_url = {}

    def fake_get(url, params=None, timeout=None):
        captured_url["url"] = url
        return FakeResp({"result": {"data": [{"i": "BTC_USDT", "a": "100"}]}})

    monkeypatch.setattr(requests, "get", fake_get)
    crypto_com.get_ticker("BTC_USDT")
    assert "get-tickers" in captured_url["url"]
    assert "get-ticker?" not in captured_url["url"]


def test_binance_candlestick(monkeypatch):
    from market_analysis_by_chrisx47b.sources import binance
    binance.get_candlestick.cache_clear()

    rows = [[NOW_MS - (4 - i) * 3600000, "100", "101", "99", "100.5", "10",
              0, "0", 1, "0", "0", "0"] for i in range(5)]
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResp(rows))
    df = binance.get_candlestick("BTCUSDT", "1h", 5)
    assert len(df) == 5
    assert df.index.is_monotonic_increasing


def test_bybit_candlestick_reverses_descending_order(monkeypatch):
    """Regressionstest: Bybit liefert absteigend, Code muss umdrehen."""
    from market_analysis_by_chrisx47b.sources import bybit
    bybit.get_candlestick.cache_clear()

    rows_desc = [[str(NOW_S - i * 3600), "100", "101", "99", "100.5", "10", "1000"] for i in range(5)]
    data = {"retCode": 0, "retMsg": "OK", "result": {"list": rows_desc}}
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResp(data))
    df = bybit.get_candlestick("BTCUSDT", "1h", 5, category="spot")
    assert df.index.is_monotonic_increasing


def test_bybit_raises_on_error_retcode(monkeypatch):
    from market_analysis_by_chrisx47b.sources import bybit
    data = {"retCode": 10001, "retMsg": "params error"}
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResp(data))
    with pytest.raises(RuntimeError, match="params error"):
        bybit.get_ticker("BTCUSDT")


def test_kucoin_column_order_close_before_high_low(monkeypatch):
    """Regressionstest: KuCoin-Spaltenreihenfolge ist time,open,CLOSE,high,low,vol,turnover."""
    from market_analysis_by_chrisx47b.sources import kucoin
    kucoin.get_candlestick.cache_clear()

    rows_desc = [[str(NOW_S - i * 3600), "100", "102", "103", "98", "10", "1000"] for i in range(5)]
    data = {"code": "200000", "data": rows_desc}
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResp(data))
    df = kucoin.get_candlestick("BTC-USDT", "1h", 5)
    last = df.iloc[-1]
    assert last["close"] == 102.0  # nicht 103 (das waere high, falsch gemappt)
    assert last["high"] == 103.0
    assert df.index.is_monotonic_increasing


def test_kraken_uses_first_non_last_key(monkeypatch):
    """Regressionstest: Kraken-Antwort-Key kann vom angefragten Symbol abweichen."""
    from market_analysis_by_chrisx47b.sources import kraken
    kraken.get_candlestick.cache_clear()

    rows_asc = [[NOW_S - (4 - i) * 3600, "100", "101", "99", "100.5", "100.2", "10", 5] for i in range(5)]
    data = {"error": [], "result": {"XXBTZUSD": rows_asc, "last": NOW_S}}
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResp(data))
    df = kraken.get_candlestick("XBTUSD", "1h", 5)
    assert len(df) == 5
    assert df.index.is_monotonic_increasing


def test_kraken_raises_on_error(monkeypatch):
    from market_analysis_by_chrisx47b.sources import kraken
    data = {"error": ["EQuery:Unknown asset pair"], "result": {}}
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResp(data))
    with pytest.raises(RuntimeError, match="Unknown asset pair"):
        kraken.get_ticker("FOOBAR")


def test_bitfinex_column_order_close_before_high_low(monkeypatch):
    """Regressionstest: Bitfinex-Spaltenreihenfolge ist MTS,OPEN,CLOSE,HIGH,LOW,VOLUME."""
    from market_analysis_by_chrisx47b.sources import bitfinex
    bitfinex.get_candlestick.cache_clear()

    rows_asc = [[NOW_MS - (4 - i) * 3600000, 100, 102, 103, 98, 10] for i in range(5)]
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResp(rows_asc))
    df = bitfinex.get_candlestick("tBTCUSD", "1h", 5)
    last = df.iloc[-1]
    assert last["close"] == 102.0
    assert last["high"] == 103.0


def test_bitfinex_adds_t_prefix(monkeypatch):
    from market_analysis_by_chrisx47b.sources import bitfinex
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        return FakeResp([[NOW_MS, 100, 100.5, 101, 99, 10]])

    monkeypatch.setattr(requests, "get", fake_get)
    bitfinex.get_candlestick("BTCUSD", "1h", 1)  # ohne 't'-Praefix
    assert "tBTCUSD" in captured["url"]


def test_coingecko_ohlc_parsing(monkeypatch):
    from market_analysis_by_chrisx47b.sources import coingecko
    coingecko.get_candlestick.cache_clear()

    rows = [[NOW_MS - (4 - i) * 3600000, 100, 101, 99, 100.5] for i in range(5)]
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResp(rows))
    df = coingecko.get_candlestick("bitcoin", "1h", 5)
    assert len(df) == 5
    assert df["close"].iloc[-1] == 100.5


def test_yahoo_chart_parsing(monkeypatch):
    from market_analysis_by_chrisx47b.sources import yahoo
    yahoo.get_candlestick.cache_clear()

    data = {"chart": {"result": [{
        "timestamp": [NOW_S - (4 - i) * 3600 for i in range(5)],
        "indicators": {"quote": [{"open": [100]*5, "high": [101]*5, "low": [99]*5,
                                   "close": [100.5]*5, "volume": [10]*5}]},
        "meta": {"regularMarketPrice": 100.5},
    }], "error": None}}
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResp(data))
    df = yahoo.get_candlestick("AAPL", "1d", 5)
    assert len(df) == 5
    assert df.index.is_monotonic_increasing


def test_yahoo_raises_on_empty_result(monkeypatch):
    from market_analysis_by_chrisx47b.sources import yahoo
    data = {"chart": {"result": None, "error": {"description": "No data found"}}}
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResp(data))
    with pytest.raises(RuntimeError, match="No data found"):
        yahoo.get_candlestick("NOTASYMBOL", "1d", 5)


def test_source_router_unknown_source_raises():
    from market_analysis_by_chrisx47b import source_router
    with pytest.raises(ValueError, match="Unbekannte Quelle"):
        source_router.get_candles("not_a_real_source", "X")


def test_source_router_supports_9_sources():
    from market_analysis_by_chrisx47b.source_router import SUPPORTED_SOURCES
    assert len(SUPPORTED_SOURCES) == 9
