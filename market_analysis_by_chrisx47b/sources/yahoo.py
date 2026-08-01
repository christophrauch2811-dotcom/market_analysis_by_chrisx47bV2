"""
Anbindung an Yahoo Finances inoffiziellen "v8 chart"-Endpunkt.

WICHTIG: Yahoos offizielle Public-API wurde 2017 eingestellt. Der
v8/finance/chart-Endpunkt ist derselbe, den Yahoos eigene Website nutzt --
inoffiziell, kein API-Key, aber Grauzone wie bei TradingView (kann sich
jederzeit aendern, kein SLA). Deckt dafuer Aktien/ETFs/Indizes/Forex/Krypto
ab -- eine andere Anlageklasse als die 5 Krypto-Boersen in diesem Connector.

Symbol-Beispiele: 'AAPL' (Aktie), 'EURUSD=X' (Forex), 'BTC-USD' (Krypto),
'^GSPC' (S&P 500 Index).
"""

import requests
import pandas as pd

from ..cache import ttl_cache, RateLimiter, retry_with_backoff

BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

TIMEFRAME_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "60m", "1d": "1d", "1w": "1wk", "1M": "1mo",
}
# Yahoo hat kein natives 4h-Intervall -- naechstbeste Naeherung.
_RANGE_FOR_COUNT = {
    "1m": "1d", "5m": "5d", "15m": "5d", "30m": "1mo",
    "1h": "3mo", "1d": "2y", "1w": "5y", "1M": "10y",
}

yahoo_limiter = RateLimiter(max_calls=10, per_seconds=1.0)


@retry_with_backoff(max_attempts=3, base_delay=1.0)
def _get(symbol: str, params: dict) -> dict:
    yahoo_limiter.acquire()
    resp = requests.get(f"{BASE_URL}/{symbol}", params=params, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    payload = resp.json()
    result = payload.get("chart", {}).get("result")
    if not result:
        error = payload.get("chart", {}).get("error", {})
        raise RuntimeError(f"Yahoo-Finance-Fehler fuer '{symbol}': {error or 'kein Ergebnis'}")
    return result[0]


@ttl_cache(seconds=30)
def get_candlestick(symbol: str, timeframe: str = "1h", count: int = 200) -> pd.DataFrame:
    """symbol z.B. 'AAPL', 'EURUSD=X', 'BTC-USD', '^GSPC'."""
    interval = TIMEFRAME_MAP.get(timeframe, "60m")
    rng = _RANGE_FOR_COUNT.get(timeframe, "3mo")
    result = _get(symbol, {"range": rng, "interval": interval})

    timestamps = result.get("timestamp")
    if not timestamps:
        raise RuntimeError(f"Keine Kerzen fuer {symbol}/{timeframe} von Yahoo Finance erhalten.")
    quote = result["indicators"]["quote"][0]

    df = pd.DataFrame({
        "timestamp": pd.to_datetime(timestamps, unit="s"),
        "open": quote["open"], "high": quote["high"], "low": quote["low"],
        "close": quote["close"], "volume": quote["volume"],
    }).set_index("timestamp").dropna(subset=["close"])
    return df.tail(count).astype(float)


@ttl_cache(seconds=15)
def get_ticker(symbol: str) -> dict:
    """Kein dediziertes Ticker-Endpoint bei Yahoo -- Meta-Feld des Chart-Aufrufs
    (regularMarketPrice, previousClose etc.) wird als Ticker-Ersatz genutzt."""
    result = _get(symbol, {"range": "1d", "interval": "1d"})
    return result.get("meta", {})
