"""
Anbindung an die oeffentliche Bybit v5 REST-API.
Keine Authentifizierung noetig fuer Marktdaten (Candles, Ticker, Orderbook).
Doku: https://bybit-exchange.github.io/docs/v5/market/kline

WICHTIG (per Doku verifiziert, nicht angenommen):
  - Bybit sortiert Kerzen ABSTEIGEND nach startTime (neueste zuerst) --
    wir drehen die Reihenfolge um, damit sie zum Rest des Connectors passt.
  - Jeder Markt-Endpunkt braucht den Parameter `category`
    ('spot', 'linear', 'inverse', 'option').
"""

import requests
import pandas as pd

from ..cache import ttl_cache, RateLimiter, retry_with_backoff

BASE_URL = "https://api.bybit.com"

INTERVAL_MAP = {
    "1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30",
    "1h": "60", "2h": "120", "4h": "240", "6h": "360", "12h": "720",
    "1d": "D", "1w": "W", "1M": "M",
}

bybit_limiter = RateLimiter(max_calls=15, per_seconds=1.0)


@retry_with_backoff(max_attempts=3, base_delay=1.0)
def _get(path: str, params: dict) -> dict:
    bybit_limiter.acquire()
    resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=10)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("retCode") != 0:
        raise RuntimeError(f"Bybit-API-Fehler ({payload.get('retCode')}): {payload.get('retMsg')}")
    return payload["result"]


@ttl_cache(seconds=30)
def get_candlestick(symbol: str, timeframe: str = "1h", count: int = 200, category: str = "spot") -> pd.DataFrame:
    """
    symbol: z.B. 'BTCUSDT'
    timeframe: einer der Keys in INTERVAL_MAP
    category: 'spot', 'linear' (USDT-Perpetuals), 'inverse', 'option'
    """
    interval = INTERVAL_MAP.get(timeframe, "60")
    result = _get("/v5/market/kline", {"category": category, "symbol": symbol, "interval": interval, "limit": count})
    rows = result["list"]  # [startTime, open, high, low, close, volume, turnover], neueste zuerst
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"])
    df["timestamp"] = pd.to_datetime(df["timestamp"].astype("int64"), unit="ms")
    df = df.set_index("timestamp").sort_index()  # Bybit liefert absteigend -> umdrehen
    return df[["open", "high", "low", "close", "volume"]].astype(float)


@ttl_cache(seconds=5)
def get_ticker(symbol: str, category: str = "spot") -> dict:
    result = _get("/v5/market/tickers", {"category": category, "symbol": symbol})
    data = result.get("list", [])
    return data[0] if data else {}


@ttl_cache(seconds=5)
def get_order_book(symbol: str, depth: int = 50, category: str = "spot") -> dict:
    return _get("/v5/market/orderbook", {"category": category, "symbol": symbol, "limit": depth})


@ttl_cache(seconds=3600)
def list_instruments(category: str = "spot") -> list:
    result = _get("/v5/market/instruments-info", {"category": category})
    return result.get("list", [])
