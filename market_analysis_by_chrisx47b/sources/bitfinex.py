"""
Anbindung an die oeffentliche Bitfinex v2 Public-API (api-pub.bitfinex.com,
getrennt von der authentifizierten api.bitfinex.com -- Public braucht keinen Key).

WICHTIG (per Doku verifiziert): Symbole brauchen ein 't'-Praefix fuer
Trading-Paare (z.B. 'tBTCUSD', nicht 'BTCUSD'). Candles-Antwort hat die
Reihenfolge [MTS, OPEN, CLOSE, HIGH, LOW, VOLUME] -- close vor high/low.
Standard-Sortierung ist absteigend (neueste zuerst); wir fordern per
sort=1 explizit aufsteigend an.
"""

import requests
import pandas as pd

from ..cache import ttl_cache, RateLimiter, retry_with_backoff

BASE_URL = "https://api-pub.bitfinex.com/v2"

TIMEFRAME_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "3h": "3h", "6h": "6h", "12h": "12h",
    "1d": "1D", "1w": "7D", "1M": "1M",
}

bitfinex_limiter = RateLimiter(max_calls=15, per_seconds=60.0)  # Doku: 10-90 Requests/Minute je Endpunkt, konservatives unteres Ende gewaehlt


def _ensure_prefix(symbol: str) -> str:
    return symbol if symbol.startswith(("t", "f")) else f"t{symbol}"


@retry_with_backoff(max_attempts=3, base_delay=1.0)
def _get(path: str, params: dict | None = None) -> object:
    bitfinex_limiter.acquire()
    resp = requests.get(f"{BASE_URL}{path}", params=params or {}, timeout=10)
    resp.raise_for_status()
    return resp.json()


@ttl_cache(seconds=30)
def get_candlestick(symbol: str, timeframe: str = "1h", count: int = 200) -> pd.DataFrame:
    """symbol z.B. 'tBTCUSD' oder 'BTCUSD' (t-Praefix wird automatisch ergaenzt)."""
    sym = _ensure_prefix(symbol)
    tf = TIMEFRAME_MAP.get(timeframe, "1h")
    rows = _get(f"/candles/trade:{tf}:{sym}/hist", {"limit": count, "sort": 1})
    # Spalten laut Doku: MTS, OPEN, CLOSE, HIGH, LOW, VOLUME -- close vor high/low
    df = pd.DataFrame(rows, columns=["timestamp", "open", "close", "high", "low", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"].astype("int64"), unit="ms")
    return df.set_index("timestamp")[["open", "high", "low", "close", "volume"]].astype(float)


@ttl_cache(seconds=5)
def get_ticker(symbol: str) -> dict:
    sym = _ensure_prefix(symbol)
    data = _get(f"/ticker/{sym}")
    # Trading-Paare: [BID, BID_SIZE, ASK, ASK_SIZE, DAILY_CHANGE, DAILY_CHANGE_PERC,
    #                 LAST_PRICE, VOLUME, HIGH, LOW]
    keys = ["bid", "bid_size", "ask", "ask_size", "daily_change", "daily_change_perc",
            "last_price", "volume", "high", "low"]
    return dict(zip(keys, data))


@ttl_cache(seconds=5)
def get_order_book(symbol: str, depth: int = 25) -> dict:
    sym = _ensure_prefix(symbol)
    data = _get(f"/book/{sym}/P0", {"len": depth})
    bids = [{"price": r[0], "count": r[1], "amount": r[2]} for r in data if r[2] > 0]
    asks = [{"price": r[0], "count": r[1], "amount": r[2]} for r in data if r[2] < 0]
    return {"bids": bids, "asks": asks}
