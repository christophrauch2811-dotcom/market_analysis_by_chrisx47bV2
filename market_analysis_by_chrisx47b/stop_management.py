"""
Stop-Loss- und Trailing-Stop-Berechnungen.

WICHTIG: Dieses Modul berechnet Stop-/Take-Profit-LEVEL fuer den aktuellen
Zeitpunkt -- es simuliert NICHT, wie sich ein Trade historisch entwickelt
haette (das waere ein Backtest, ausdruecklich nicht gewuenscht). Jede
Funktion ist eine zustandslose Berechnung: gegeben aktuelle Daten (+ ggf.
vorheriger Stop), was ist das naechste sinnvolle Level.
"""

from __future__ import annotations
import pandas as pd
import ta


def _atr(df: pd.DataFrame, window: int = 14) -> float:
    return float(ta.volatility.average_true_range(df["high"], df["low"], df["close"], window=window).iloc[-1])


# ---------------------------------------------------------------------------
# Initiale Stop-Loss-Methoden
# ---------------------------------------------------------------------------

def fixed_percent_stop(entry_price: float, side: str, pct: float = 1.0) -> float:
    """side: 'long' oder 'short'. pct in Prozent (1.0 = 1%)."""
    if side == "long":
        return round(entry_price * (1 - pct / 100), 6)
    return round(entry_price * (1 + pct / 100), 6)


def atr_stop(df: pd.DataFrame, entry_price: float, side: str, atr_mult: float = 1.5, atr_window: int = 14) -> dict:
    atr = _atr(df, atr_window)
    stop = entry_price - atr_mult * atr if side == "long" else entry_price + atr_mult * atr
    return {"stop_price": round(stop, 6), "atr": round(atr, 6), "atr_mult": atr_mult}


def structure_stop(df: pd.DataFrame, side: str, lookback: int = 20, buffer_pct: float = 0.1) -> dict:
    """Stop knapp unter/ueber dem letzten Swing-Low/-High (buffer_pct = Sicherheitsabstand in %)."""
    if side == "long":
        level = df["low"].tail(lookback).min()
        stop = level * (1 - buffer_pct / 100)
    else:
        level = df["high"].tail(lookback).max()
        stop = level * (1 + buffer_pct / 100)
    return {"stop_price": round(float(stop), 6), "structure_level": round(float(level), 6), "lookback": lookback}


def take_profit_from_r_multiple(entry_price: float, stop_price: float, side: str, r_multiple: float = 2.0) -> float:
    """Take-Profit auf Basis eines Risk/Reward-Vielfachen (R = Abstand entry<->stop)."""
    r = abs(entry_price - stop_price)
    if side == "long":
        return round(entry_price + r * r_multiple, 6)
    return round(entry_price - r * r_multiple, 6)


# ---------------------------------------------------------------------------
# Trailing-Stop-Methoden
# ---------------------------------------------------------------------------

def chandelier_exit(df: pd.DataFrame, side: str, atr_mult: float = 3.0, lookback: int = 22) -> dict:
    """Klassischer Chandelier Exit: Long = hoechstes Hoch im Lookback - ATR*mult;
    Short = tiefstes Tief im Lookback + ATR*mult."""
    atr = _atr(df)
    if side == "long":
        anchor = df["high"].tail(lookback).max()
        stop = anchor - atr_mult * atr
    else:
        anchor = df["low"].tail(lookback).min()
        stop = anchor + atr_mult * atr
    return {"stop_price": round(float(stop), 6), "anchor_price": round(float(anchor), 6), "atr": round(atr, 6)}


def percent_trailing_stop(extreme_price_since_entry: float, side: str, trail_pct: float = 2.0) -> float:
    """extreme_price_since_entry: hoechster Preis seit Entry (long) bzw.
    tiefster Preis seit Entry (short) -- muss der Aufrufer selbst tracken,
    da dieses Modul keinen Trade-Zustand ueber Zeit haelt."""
    if side == "long":
        return round(extreme_price_since_entry * (1 - trail_pct / 100), 6)
    return round(extreme_price_since_entry * (1 + trail_pct / 100), 6)


def update_trailing_stop(current_stop: float, proposed_stop: float, side: str) -> float:
    """Ratchet-Logik: ein Trailing-Stop darf sich NIE gegen die Position
    bewegen (nur enger/besser werden, nie lockerer). Long: Stop darf nur
    steigen. Short: Stop darf nur fallen.
    """
    if side == "long":
        return max(current_stop, proposed_stop)
    return min(current_stop, proposed_stop)


def move_to_breakeven(entry_price: float, current_price: float, side: str,
                       current_stop: float, trigger_r_multiple: float = 1.0,
                       initial_risk: float | None = None, breakeven_buffer_pct: float = 0.05) -> dict:
    """Verschiebt den Stop auf Breakeven (+ kleinem Puffer), sobald der Preis
    ein bestimmtes Vielfaches des initialen Risikos (initial_risk = |entry-stop|
    beim Einstieg) erreicht hat. Gibt zurueck, ob getriggert wurde und das neue Level.
    """
    risk = initial_risk if initial_risk is not None else abs(entry_price - current_stop)
    if risk == 0:
        return {"triggered": False, "stop_price": current_stop}

    move = (current_price - entry_price) if side == "long" else (entry_price - current_price)
    triggered = move >= risk * trigger_r_multiple
    if not triggered:
        return {"triggered": False, "stop_price": current_stop}

    buffer = entry_price * breakeven_buffer_pct / 100
    new_stop = entry_price + buffer if side == "long" else entry_price - buffer
    new_stop = update_trailing_stop(current_stop, new_stop, side)
    return {"triggered": True, "stop_price": round(new_stop, 6)}


# ---------------------------------------------------------------------------
# Kombinierter Plan (ein Snapshot, keine Zeitreihen-Simulation)
# ---------------------------------------------------------------------------

def compute_stop_plan(df: pd.DataFrame, entry_price: float, side: str,
                       stop_method: str = "atr", atr_mult: float = 1.5,
                       trail_method: str = "chandelier", trail_atr_mult: float = 3.0,
                       r_multiple_tp: float = 2.0) -> dict:
    """Baut einen vollstaendigen Stop-Plan fuer den JETZIGEN Zeitpunkt:
    initialer Stop, Take-Profit (R-Vielfaches), aktuelles Trailing-Stop-Level.
    Kein Zustand, keine Historie -- bei jedem Aufruf neu aus den aktuellen
    Daten berechnet. Fuer echtes Nachziehen ueber Zeit muss der Aufrufer
    current_stop selbst zwischenspeichern und bei jedem neuen Preis
    update_trailing_stop() aufrufen.
    """
    if stop_method == "structure":
        initial = structure_stop(df, side)
    else:
        initial = atr_stop(df, entry_price, side, atr_mult)

    take_profit = take_profit_from_r_multiple(entry_price, initial["stop_price"], side, r_multiple_tp)

    if trail_method == "chandelier":
        trailing = chandelier_exit(df, side, trail_atr_mult)
    else:
        extreme = df["high"].max() if side == "long" else df["low"].min()
        trailing = {"stop_price": percent_trailing_stop(float(extreme), side, trail_atr_mult)}

    return {
        "side": side, "entry_price": entry_price,
        "initial_stop": initial, "take_profit": take_profit,
        "current_trailing_stop": trailing,
        "note": "Snapshot-Berechnung fuer den aktuellen Zeitpunkt, keine Trade-Simulation.",
    }
