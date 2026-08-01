"""
Anbindung an die oeffentliche KuCoin-Spot-API. Public Endpoints brauchen
KEINEN API-Key (verifiziert -- offizielle Doku + mehrere unabhaengige Quellen).

WICHTIG (per Doku verifiziert, nicht angenommen): Die Kline-Antwort hat eine
unuebliche Spaltenreihenfolge: [time, open, CLOSE, high, low, volume, turnover]
-- close steht vor high/low, nicht danach wie bei den anderen Quellen.
"""

import requests
import pandas as pd

from ..cache import ttl_cache, RateLimiter, retry_with_backoff

BASE_URL = "https://api.kucoin.com"

TIMEFRAME_MAP = {
    "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min", "30m": "30min",
    "1h": "1hour", "2h": "2hour", "4h": "4hour", "6h": "6hour", "8h": "8hour",
    "12h": "12hour", "1d": "1day", "1w": "1week",
}

kucoin_limiter = RateLimiter(max_calls=10, per_seconds=1.0)  # kein exaktes oeffentliches IP-Limit dokumentiert -- konservative Schaetzung


@retry_with_backoff(max_attempts=3, base_delay=1.0)
def _get(path: str, params: dict) -> dict:
    kucoin_limiter.acquire()
    resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=10)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("code") != "200000":
        raise RuntimeError(f"KuCoin-API-Fehler ({payload.get('code')}): {payload.get('msg')}")
    return payload["data"]


@ttl_cache(seconds=30)
def get_candlestick(symbol: str, timeframe: str = "1h", count: int = 200) -> pd.DataFrame:
    """symbol z.B. 'BTC-USDT' (mit Bindestrich, nicht 'BTCUSDT')."""
    interval = TIMEFRAME_MAP.get(timeframe, "1hour")
    rows = _get("/api/v1/market/candles", {"symbol": symbol, "type": interval})
    if not rows:
        raise RuntimeError(f"Keine Kerzen fuer {symbol}/{timeframe} von KuCoin erhalten.")
    rows = rows[:count]
    # Spaltenreihenfolge laut Doku: time, open, close, high, low, volume, turnover
    df = pd.DataFrame(rows, columns=["timestamp", "open", "close", "high", "low", "volume", "turnover"])
    df["timestamp"] = pd.to_datetime(df["timestamp"].astype("int64"), unit="s")
    df = df.set_index("timestamp").sort_index()  # KuCoin liefert neueste zuerst -> umdrehen
    return df[["open", "high", "low", "close", "volume"]].astype(float)


@ttl_cache(seconds=5)
def get_ticker(symbol: str) -> dict:
    """symbol z.B. 'BTC-USDT'. Level-1: bestes Bid/Ask + letzter Preis."""
    return _get("/api/v1/market/orderbook/level1", {"symbol": symbol})
