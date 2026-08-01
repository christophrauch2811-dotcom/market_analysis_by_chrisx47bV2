"""
Anbindung an die oeffentliche Kraken-API. Public Endpoints brauchen keinen Key.

WICHTIG (per Doku verifiziert): Kraken gibt den Ergebnis-Key oft unter einem
INTERNEN Pair-Namen zurueck, der vom angefragten Symbol abweicht (z.B.
angefragt 'XBTUSD', Antwort-Key 'XXBTZUSD'). Wir nehmen deshalb den ersten
Key im result-Dict, der nicht 'last' heisst, statt den angefragten Namen
direkt zu erwarten.
"""

import requests
import pandas as pd

from ..cache import ttl_cache, RateLimiter, retry_with_backoff

BASE_URL = "https://api.kraken.com/0"

# Kraken-Intervalle sind Minuten; gueltige Werte: 1,5,15,30,60,240,1440,10080,604800
TIMEFRAME_MAP = {
    "1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60,
    "4h": 240, "1d": 1440, "1w": 10080,
}

kraken_limiter = RateLimiter(max_calls=1, per_seconds=1.0)  # Krakens eigene Empfehlung: 1 Request/Sekunde oder weniger


@retry_with_backoff(max_attempts=3, base_delay=1.0)
def _get(path: str, params: dict) -> dict:
    kraken_limiter.acquire()
    resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=10)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("error"):
        raise RuntimeError(f"Kraken-API-Fehler: {payload['error']}")
    return payload["result"]


def _first_pair_key(result: dict) -> str:
    """Kraken antwortet mit einem internen Pair-Namen, der vom angefragten
    Symbol abweichen kann -- ersten Key nehmen, der nicht 'last' heisst."""
    for key in result:
        if key != "last":
            return key
    raise RuntimeError("Kraken-Antwort enthielt keinen Pair-Key.")


@ttl_cache(seconds=60)
def get_candlestick(symbol: str, timeframe: str = "1h", count: int = 200) -> pd.DataFrame:
    """symbol z.B. 'XBTUSD' (Kraken nutzt 'XBT' statt 'BTC')."""
    interval = TIMEFRAME_MAP.get(timeframe, 60)
    result = _get("/public/OHLC", {"pair": symbol, "interval": interval})
    pair_key = _first_pair_key(result)
    rows = result[pair_key][-count:]
    # Spalten laut Doku: time, open, high, low, close, vwap, volume, count
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "vwap", "volume", "n_trades"])
    df["timestamp"] = pd.to_datetime(df["timestamp"].astype("int64"), unit="s")
    return df.set_index("timestamp")[["open", "high", "low", "close", "volume"]].astype(float)


@ttl_cache(seconds=5)
def get_ticker(symbol: str) -> dict:
    result = _get("/public/Ticker", {"pair": symbol})
    return result[_first_pair_key(result)]


@ttl_cache(seconds=5)
def get_order_book(symbol: str, depth: int = 50) -> dict:
    result = _get("/public/Depth", {"pair": symbol, "count": depth})
    return result[_first_pair_key(result)]
