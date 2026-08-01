"""
Live-Verifikations-Skript. Testet ALLE Quellen + News-Filter + die neuen
Module (symbol_map, compare_sources) mit ECHTEN Netzwerkaufrufen -- das kann
nur lokal bei dir laufen (aus der Build-Sandbox nicht moeglich).

Ausfuehren:
    pip install -e .
    python verify_live_data.py

Gibt eine Zusammenfassung (OK/FEHLER je Quelle) am Ende aus. Ein Fehlschlag
bei einer einzelnen Quelle stoppt nicht das ganze Skript.
"""

import sys
import traceback

results = {}


def check(name, fn):
    try:
        value = fn()
        results[name] = ("OK", value)
        print(f"[OK]    {name}: {value}")
    except Exception as e:
        results[name] = ("FEHLER", str(e))
        print(f"[FEHLER] {name}: {e}")
        if "--verbose" in sys.argv:
            traceback.print_exc()


print("=" * 70)
print("1) DATENQUELLEN -- Candles")
print("=" * 70)

from market_analysis_by_chrisx47b.sources import (
    crypto_com, binance, bybit, kucoin, kraken, bitfinex, coingecko, yahoo, tradingview,
)

check("crypto_com.candles", lambda: len(crypto_com.get_candlestick("BTC_USDT", "1h", 20)))
check("binance.candles", lambda: len(binance.get_candlestick("BTCUSDT", "1h", 20)))
check("bybit.candles", lambda: len(bybit.get_candlestick("BTCUSDT", "1h", 20)))
check("kucoin.candles", lambda: len(kucoin.get_candlestick("BTC-USDT", "1h", 20)))
check("kraken.candles", lambda: len(kraken.get_candlestick("XBTUSD", "1h", 20)))
check("bitfinex.candles", lambda: len(bitfinex.get_candlestick("tBTCUSD", "1h", 20)))
check("coingecko.candles", lambda: len(coingecko.get_candlestick("bitcoin", "1h", 20)))
check("yahoo.candles", lambda: len(yahoo.get_candlestick("AAPL", "1d", 20)))

print()
print("=" * 70)
print("2) DATENQUELLEN -- Ticker")
print("=" * 70)

check("crypto_com.ticker", lambda: crypto_com.get_ticker("BTC_USDT").get("a"))
check("binance.ticker", lambda: binance.get_ticker("BTCUSDT").get("lastPrice"))
check("bybit.ticker", lambda: bybit.get_ticker("BTCUSDT").get("lastPrice"))
check("kucoin.ticker", lambda: kucoin.get_ticker("BTC-USDT").get("price"))
check("kraken.ticker", lambda: kraken.get_ticker("XBTUSD").get("c"))
check("bitfinex.ticker", lambda: bitfinex.get_ticker("tBTCUSD").get("last_price"))
check("coingecko.ticker", lambda: coingecko.get_ticker("bitcoin"))
check("yahoo.ticker", lambda: yahoo.get_ticker("AAPL").get("regularMarketPrice"))

print()
print("=" * 70)
print("3) TRADINGVIEW")
print("=" * 70)

check("tradingview.summary", lambda: tradingview.get_technical_summary(
    "BTCUSDT", "BINANCE", "crypto", "1h")["summary"])

print()
print("=" * 70)
print("4) NEWS-FILTER (RSS)")
print("=" * 70)

from market_analysis_by_chrisx47b.news_filter import get_filtered_news

check("news_filter.rss", lambda: len(get_filtered_news(keywords=["bitcoin"], hours=48)))

print()
print("=" * 70)
print("5) SYMBOL-MAPPING (Punkt 1) + COMPARE_SOURCES (Punkt 2)")
print("=" * 70)

from market_analysis_by_chrisx47b import server

check("symbol_map.mapping", lambda: __import__(
    "market_analysis_by_chrisx47b.symbol_map", fromlist=["to_source_symbol"]
).to_source_symbol("BTC/USDT", "kraken"))

check("compare_sources.live", lambda: server.mcp._tool_manager._tools["compare_sources"].fn(
    canonical_symbol="BTC/USDT", sources=["binance", "bybit", "kraken"]
)["spread"])

print()
print("=" * 70)
print("6) ANALYSE-MODULE MIT ECHTEN CRYPTO.COM-DATEN")
print("=" * 70)

from market_analysis_by_chrisx47b.rl_features import build_model_feature_vector
from market_analysis_by_chrisx47b.regime import detect_regime
from market_analysis_by_chrisx47b.chart_patterns import detect_chart_patterns
from market_analysis_by_chrisx47b.extended_indicators import compute_extended_indicators

check("rl_features (echte Daten)", lambda: len(build_model_feature_vector(
    crypto_com.get_candlestick("BTC_USDT", "1h", 300))))
check("regime (echte Daten)", lambda: detect_regime(
    crypto_com.get_candlestick("BTC_USDT", "1h", 300))["regime_label"])
check("chart_patterns (echte Daten)", lambda: len(detect_chart_patterns(
    crypto_com.get_candlestick("BTC_USDT", "1h", 300))))
check("extended_indicators (echte Daten)", lambda: compute_extended_indicators(
    crypto_com.get_candlestick("BTC_USDT", "1h", 200))["supertrend_direction"])

print()
print("=" * 70)
print("ZUSAMMENFASSUNG")
print("=" * 70)
ok_count = sum(1 for status, _ in results.values() if status == "OK")
total = len(results)
print(f"{ok_count}/{total} erfolgreich")
for name, (status, value) in results.items():
    marker = "OK" if status == "OK" else "FEHLER"
    print(f"  [{marker:6s}] {name}")

if ok_count < total:
    print()
    print("Bei FEHLER-Zeilen: mit --verbose erneut ausfuehren fuer den vollen")
    print("Traceback, oder den Fehlertext direkt zurueckschicken.")
    sys.exit(1)
