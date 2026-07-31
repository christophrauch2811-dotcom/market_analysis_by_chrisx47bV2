"""
Anbindung an die oeffentliche Crypto.com Exchange REST-API.
Keine Authentifizierung noetig fuer Marktdaten (Candles, Ticker, Orderbook, Trades).
Doku: https://exchange-docs.crypto.com/exchange/v1/rest-ws/index.html
"""

import requests
import pandas as pd

BASE_URL = "https://api.crypto.com/exchange/v1"

TIMEFRAME_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "4h": "4h", "1d": "1D", "1w": "7D", "1M": "1M",
}


def get_candlestick(symbol: str, timeframe: str = "1h", count: int = 200) -> pd.DataFrame:
    """
    symbol: z.B. 'BTCUSD-PERP' oder 'BTC_USDT'
    timeframe: einer der Keys in TIMEFRAME_MAP
    """
    tf = TIMEFRAME_MAP.get(timeframe, "1h")
    resp = requests.get(
        f"{BASE_URL}/public/get-candlestick",
        params={"instrument_name": symbol, "timeframe": tf, "count": count},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()["result"]["data"]
    df = pd.DataFrame(data)
    df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume", "t": "timestamp"})
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.set_index("timestamp").astype(float, errors="ignore")
    return df[["open", "high", "low", "close", "volume"]].astype(float)


def get_ticker(symbol: str) -> dict:
    resp = requests.get(f"{BASE_URL}/public/get-ticker", params={"instrument_name": symbol}, timeout=10)
    resp.raise_for_status()
    return resp.json()["result"]["data"][0]


def get_order_book(symbol: str, depth: int = 10) -> dict:
    resp = requests.get(
        f"{BASE_URL}/public/get-book", params={"instrument_name": symbol, "depth": depth}, timeout=10
    )
    resp.raise_for_status()
    return resp.json()["result"]["data"][0]


def list_instruments() -> list:
    resp = requests.get(f"{BASE_URL}/public/get-instruments", timeout=10)
    resp.raise_for_status()
    return resp.json()["result"]["data"]
