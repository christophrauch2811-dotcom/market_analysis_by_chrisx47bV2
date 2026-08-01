"""
Zentraler Dispatcher fuer alle Datenquellen. Ziel: server.py (und zukuenftige
Connectoren) rufen EINE Funktion auf statt in jedem Tool ein if/elif ueber
alle Quellen zu wiederholen. Neue Quelle hinzufuegen = hier einen Eintrag
ergaenzen, nicht jedes einzelne Tool anfassen.
"""

from __future__ import annotations
import pandas as pd

from .sources import crypto_com, binance, bybit, mt5_source

SUPPORTED_SOURCES = ("crypto", "binance", "bybit", "mt5")


def get_candles(source: str, symbol: str, timeframe: str = "1h", count: int = 200, **kwargs) -> pd.DataFrame:
    """kwargs: z.B. category='linear' fuer Bybit-Futures statt Spot."""
    if source == "binance":
        return binance.get_candlestick(symbol, timeframe, count)
    if source == "bybit":
        return bybit.get_candlestick(symbol, timeframe, count, category=kwargs.get("category", "spot"))
    if source == "mt5":
        return mt5_source.get_ohlcv(symbol, timeframe, count)
    if source == "crypto":
        return crypto_com.get_candlestick(symbol, timeframe, count)
    raise ValueError(f"Unbekannte Quelle '{source}'. Erlaubt: {SUPPORTED_SOURCES}")


def get_ticker(source: str, symbol: str, **kwargs) -> dict:
    if source == "binance":
        return binance.get_ticker(symbol)
    if source == "bybit":
        return bybit.get_ticker(symbol, category=kwargs.get("category", "spot"))
    if source == "crypto":
        return crypto_com.get_ticker(symbol)
    raise ValueError(f"Ticker nicht unterstuetzt fuer Quelle '{source}' (MT5: nutze mt5_account_info/mt5_open_positions).")


def get_order_book(source: str, symbol: str, depth: int = 50, **kwargs) -> dict:
    if source == "binance":
        return binance.get_order_book(symbol, depth)
    if source == "bybit":
        return bybit.get_order_book(symbol, depth, category=kwargs.get("category", "spot"))
    if source == "crypto":
        return crypto_com.get_order_book(symbol, depth)
    raise ValueError(f"Orderbuch nicht unterstuetzt fuer Quelle '{source}'.")
