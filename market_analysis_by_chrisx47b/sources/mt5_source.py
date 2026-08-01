"""
Anbindung an ein lokal laufendes MetaTrader 5 Terminal.

WICHTIG: Das offizielle 'MetaTrader5'-Paket funktioniert NUR unter Windows und
NUR wenn ein MT5-Terminal lokal installiert und eingeloggt ist. Dieser Connector
muss dafuer auf deinem eigenen Windows-Rechner laufen (nicht in einer Cloud/Linux-Sandbox).

pip install MetaTrader5
"""

import pandas as pd

from ..cache import ttl_cache

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

TIMEFRAME_MAP = {
    "1m": "TIMEFRAME_M1", "5m": "TIMEFRAME_M5", "15m": "TIMEFRAME_M15",
    "30m": "TIMEFRAME_M30", "1h": "TIMEFRAME_H1", "4h": "TIMEFRAME_H4",
    "1d": "TIMEFRAME_D1", "1w": "TIMEFRAME_W1",
}


def _ensure_available():
    if not MT5_AVAILABLE:
        raise RuntimeError(
            "MetaTrader5-Paket nicht verfuegbar. Dieser Teil des Connectors muss "
            "lokal auf einem Windows-Rechner mit installiertem MT5-Terminal laufen."
        )


def ensure_connection():
    _ensure_available()
    if not mt5.initialize():
        raise RuntimeError(f"MT5-Initialisierung fehlgeschlagen: {mt5.last_error()}")


@ttl_cache(seconds=10)
def get_ohlcv(symbol: str, timeframe: str = "1h", count: int = 200) -> pd.DataFrame:
    ensure_connection()
    tf = getattr(mt5, TIMEFRAME_MAP.get(timeframe, "TIMEFRAME_H1"))
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None:
        raise RuntimeError(f"Keine Daten fuer {symbol}: {mt5.last_error()}")
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.set_index("time").rename(columns={"tick_volume": "volume"})
    return df[["open", "high", "low", "close", "volume"]]


def get_symbol_info(symbol: str) -> dict:
    ensure_connection()
    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f"Symbol {symbol} nicht gefunden")
    return info._asdict()


def get_account_info() -> dict:
    ensure_connection()
    info = mt5.account_info()
    if info is None:
        raise RuntimeError(f"Kontoinfo nicht verfuegbar: {mt5.last_error()}")
    return info._asdict()


def get_open_positions() -> list:
    ensure_connection()
    positions = mt5.positions_get()
    if positions is None:
        return []
    return [p._asdict() for p in positions]
