"""
Anbindung an die oeffentliche Binance REST-API.
Keine Authentifizierung noetig fuer Marktdaten (Candles, Ticker, Orderbook).
Doku: https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints
"""

import requests
import pandas as pd

from ..cache import ttl_cache, RateLimiter, retry_with_backoff

BASE_URL = "https://api.binance.com"

# Binance-Intervalle sind bereits genau unsere Standard-Keys (im Gegensatz zu
# Crypto.com/Bybit) -- kein Mapping noetig, nur eine Whitelist zur Absicherung.
SUPPORTED_INTERVALS = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"}

binance_limiter = RateLimiter(max_calls=10, per_seconds=1.0)  # Doku: 6000 Weight/Min, Klines-Weight klein -> 10/s deutlich konservativ


@ttl_cache(seconds=30)
@retry_with_backoff(max_attempts=3, base_delay=1.0)
def get_candlestick(symbol: str, timeframe: str = "1h", count: int = 200) -> pd.DataFrame:
    """
    symbol: z.B. 'BTCUSDT' (Binance nutzt keine Unterstriche)
    timeframe: einer der SUPPORTED_INTERVALS-Werte
    """
    interval = timeframe if timeframe in SUPPORTED_INTERVALS else "1h"
    binance_limiter.acquire()
    resp = requests.get(
        f"{BASE_URL}/api/v3/klines",
        params={"symbol": symbol, "interval": interval, "limit": count},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    # Reihenfolge laut Doku: [openTime, open, high, low, close, volume, closeTime, ...]
    df = pd.DataFrame(data, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "n_trades", "taker_buy_base", "taker_buy_quote", "ignore",
    ])
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")
    df = df.set_index("timestamp")
    return df[["open", "high", "low", "close", "volume"]].astype(float)


@ttl_cache(seconds=5)
@retry_with_backoff(max_attempts=3, base_delay=1.0)
def get_ticker(symbol: str) -> dict:
    binance_limiter.acquire()
    resp = requests.get(f"{BASE_URL}/api/v3/ticker/24hr", params={"symbol": symbol}, timeout=10)
    resp.raise_for_status()
    return resp.json()


@ttl_cache(seconds=5)
@retry_with_backoff(max_attempts=3, base_delay=1.0)
def get_order_book(symbol: str, depth: int = 100) -> dict:
    binance_limiter.acquire()
    resp = requests.get(f"{BASE_URL}/api/v3/depth", params={"symbol": symbol, "limit": depth}, timeout=10)
    resp.raise_for_status()
    return resp.json()


@ttl_cache(seconds=3600)
@retry_with_backoff(max_attempts=3, base_delay=1.0)
def list_instruments() -> list:
    binance_limiter.acquire()
    resp = requests.get(f"{BASE_URL}/api/v3/exchangeInfo", timeout=10)
    resp.raise_for_status()
    symbols = resp.json().get("symbols", [])
    return [
        {"symbol": s["symbol"], "status": s["status"], "baseAsset": s["baseAsset"], "quoteAsset": s["quoteAsset"]}
        for s in symbols
    ]
