"""
Anbindung an ein lokal laufendes MetaTrader 5 Terminal.

WICHTIG: Das offizielle 'MetaTrader5'-Paket funktioniert NUR unter Windows und
NUR wenn ein MT5-Terminal lokal installiert und eingeloggt ist. Dieser Connector
muss dafuer auf deinem eigenen Windows-Rechner laufen (nicht in einer Cloud/Linux-Sandbox).

pip install MetaTrader5
"""

import time
from datetime import datetime, timedelta, timezone

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


@ttl_cache(seconds=3600)
def get_max_history(symbol: str, timeframe: str = "1h", years_back: float = 6.0,
                     chunk_days: int = 180, pause_seconds: float = 0.05) -> pd.DataFrame:
    """
    Holt so viel historische Kerzen wie Broker/Terminal fuer `symbol` vorhalten,
    bis zurueck zu `years_back` Jahren -- in Chunks von je `chunk_days` Tagen
    (mt5.copy_rates_range statt copy_rates_from_pos, da Einzelabfragen ueber
    mehrere Jahre je nach Terminal-Einstellung/Broker gekappt werden koennen).

    EHRLICHER HINWEIS: Wie viel Historie tatsaechlich zurueckkommt, haengt vom
    Broker ab -- manche halten fuer M1 nur wenige Monate vor, fuer H1/D1 oft
    deutlich mehr. Diese Funktion fordert `years_back` Jahre an, garantiert
    aber nicht, dass so viel existiert. Das tatsaechliche Datumsfenster steht
    im Ergebnis (df.index.min()/.max()) bzw. im 'date_range' des MCP-Tools.

    Damit das Terminal die volle Historie synchronisiert, wird das Symbol per
    symbol_select() aktiv in die Market-Watch aufgenommen (viele Broker
    liefern sonst nur einen kurzen Ausschnitt).
    """
    ensure_connection()
    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"Symbol {symbol} konnte nicht ausgewaehlt werden: {mt5.last_error()}")

    tf = getattr(mt5, TIMEFRAME_MAP.get(timeframe, "TIMEFRAME_H1"))
    date_to = datetime.now(timezone.utc)
    date_from_total = date_to - timedelta(days=int(365.25 * years_back))

    chunks = []
    cursor_end = date_to
    while cursor_end > date_from_total:
        cursor_start = max(date_from_total, cursor_end - timedelta(days=chunk_days))
        rates = mt5.copy_rates_range(symbol, tf, cursor_start, cursor_end)
        if rates is not None and len(rates) > 0:
            chunks.append(pd.DataFrame(rates))
        cursor_end = cursor_start
        if pause_seconds:
            time.sleep(pause_seconds)

    if not chunks:
        raise RuntimeError(
            f"Keine historischen Daten fuer {symbol}/{timeframe} verfuegbar "
            f"(mt5.last_error(): {mt5.last_error()}). Moeglich, dass der Broker "
            f"fuer dieses Symbol/Timeframe keine Historie in diesem Zeitraum vorhaelt."
        )

    df = pd.concat(chunks, ignore_index=True)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.drop_duplicates(subset="time").sort_values("time").set_index("time")
    df = df.rename(columns={"tick_volume": "volume"})
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
