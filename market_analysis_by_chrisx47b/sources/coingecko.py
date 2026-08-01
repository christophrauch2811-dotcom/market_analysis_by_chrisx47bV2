"""
Anbindung an die oeffentliche CoinGecko-API.

WICHTIG: CoinGecko verlangt inzwischen einen (kostenlosen) Demo-API-Key fuer
den Demo-Plan -- anders als Crypto.com/Binance/Bybit. Key ist HIER OPTIONAL:
ohne Key funktionieren manche Endpunkte noch stark rate-limitiert, mit Key
(Umgebungsvariable COINGECKO_API_KEY) zuverlaessiger. Kein Zwang, das
einzurichten -- ohne Key bekommst du ggf. haeufiger 429 Too Many Requests.

WICHTIGER STRUKTUR-UNTERSCHIED zu den anderen Quellen:
  - `symbol` ist hier die CoinGecko "Coin ID" (z.B. 'bitcoin'), NICHT ein
    Trading-Pair wie 'BTCUSDT'. Coin-IDs nachschlagen: /coins/list.
  - Es gibt keinen waehlbaren `timeframe` -- /coins/{id}/ohlc bestimmt die
    Granularitaet automatisch anhand von `days`. Wir schaetzen `days` grob
    aus timeframe+count, aber die tatsaechliche Granularitaet kann abweichen.
"""

import os
import requests
import pandas as pd

from ..cache import ttl_cache, RateLimiter, retry_with_backoff

BASE_URL = "https://api.coingecko.com/api/v3"
API_KEY = os.environ.get("COINGECKO_API_KEY", "").strip()

coingecko_limiter = RateLimiter(max_calls=25, per_seconds=60.0)  # Doku: 30 Calls/Minute im Demo-Plan, 25 als Sicherheitsabstand

# Grobe Faustregel: wie viele Tage Historie fuer count Kerzen bei timeframe anfragen,
# damit CoinGeckos automatische Granularitaet ungefaehr passt.
_HOURS_PER_BAR = {"1m": 1/60, "5m": 5/60, "15m": 15/60, "30m": 30/60,
                   "1h": 1, "4h": 4, "1d": 24, "1w": 168, "1M": 720}


def _headers() -> dict:
    return {"x-cg-demo-api-key": API_KEY} if API_KEY else {}


@retry_with_backoff(max_attempts=3, base_delay=1.0)
def _get(path: str, params: dict) -> dict:
    coingecko_limiter.acquire()
    resp = requests.get(f"{BASE_URL}{path}", params=params, headers=_headers(), timeout=10)
    resp.raise_for_status()
    return resp.json()


@ttl_cache(seconds=60)
def get_candlestick(symbol: str, timeframe: str = "1h", count: int = 200) -> pd.DataFrame:
    """symbol = CoinGecko Coin ID (z.B. 'bitcoin', NICHT 'BTCUSDT')."""
    hours_needed = _HOURS_PER_BAR.get(timeframe, 1) * count
    days = max(1, min(365, int(hours_needed / 24) + 1))
    data = _get(f"/coins/{symbol}/ohlc", {"vs_currency": "usd", "days": days})
    df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df["volume"] = float("nan")  # OHLC-Endpunkt liefert kein Volumen
    return df.set_index("timestamp")[["open", "high", "low", "close", "volume"]].astype(float)


@ttl_cache(seconds=15)
def get_ticker(symbol: str) -> dict:
    """symbol = CoinGecko Coin ID. Liefert Preis, 24h-Change, 24h-Volumen, Marketcap."""
    data = _get("/simple/price", {
        "ids": symbol, "vs_currencies": "usd",
        "include_24hr_change": "true", "include_24hr_vol": "true", "include_market_cap": "true",
    })
    return data.get(symbol, {})
