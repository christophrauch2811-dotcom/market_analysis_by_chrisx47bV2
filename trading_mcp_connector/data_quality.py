"""
Datenqualitaetspruefung fuer OHLCV-DataFrames -- BEVOR Indikatoren/Features
berechnet werden. Ziel: Probleme laut melden statt leise falsche Ergebnisse
zu produzieren (besonders wichtig bei RL-Training ueber Jahre historischer Daten).
"""

from __future__ import annotations
import numpy as np
import pandas as pd


def validate_ohlcv(df: pd.DataFrame, expected_freq: str | None = None,
                    max_single_bar_move_pct: float = 20.0) -> dict:
    """
    Prueft ein OHLCV-DataFrame auf typische Datenqualitaetsprobleme:
      - fehlende Werte (NaN)
      - doppelte Zeitstempel
      - Zeitluecken (fehlende Kerzen im erwarteten Intervall)
      - unplausible Preisspruenge (> max_single_bar_move_pct in einer Kerze)
      - OHLC-Konsistenz (high >= open/close/low, low <= open/close/high)
      - negative oder Null-Volumen (falls Spalte vorhanden)

    Gibt KEINE Exception -- liefert ein Ergebnis-dict, damit der aufrufende
    Code selbst entscheiden kann, ob er abbricht oder nur warnt.
    """
    issues = []

    if df.empty:
        return {"is_valid": False, "issues": ["DataFrame ist leer"], "row_count": 0}

    required_cols = {"open", "high", "low", "close"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        issues.append(f"Fehlende Spalten: {sorted(missing_cols)}")
        return {"is_valid": False, "issues": issues, "row_count": len(df)}

    # NaN-Werte
    nan_counts = df[list(required_cols)].isna().sum()
    nan_total = int(nan_counts.sum())
    if nan_total > 0:
        issues.append(f"{nan_total} NaN-Werte gefunden: {nan_counts[nan_counts > 0].to_dict()}")

    # Doppelte Zeitstempel
    if isinstance(df.index, pd.DatetimeIndex):
        dup_count = int(df.index.duplicated().sum())
        if dup_count > 0:
            issues.append(f"{dup_count} doppelte Zeitstempel im Index")

        # Zeitluecken
        if expected_freq is not None and len(df) > 2:
            expected_range = pd.date_range(df.index.min(), df.index.max(), freq=expected_freq)
            missing_bars = expected_range.difference(df.index)
            if len(missing_bars) > 0:
                issues.append(
                    f"{len(missing_bars)} fehlende Kerzen im erwarteten Intervall "
                    f"'{expected_freq}' (erste fehlende: {missing_bars[0]})"
                )
    else:
        issues.append("Index ist kein DatetimeIndex -- Zeitluecken-Check uebersprungen")

    # OHLC-Konsistenz
    inconsistent = (
        (df["high"] < df[["open", "close", "low"]].max(axis=1)) |
        (df["low"] > df[["open", "close", "high"]].min(axis=1))
    )
    inconsistent_count = int(inconsistent.sum())
    if inconsistent_count > 0:
        issues.append(f"{inconsistent_count} Kerzen mit inkonsistentem OHLC (high < max(o,c,l) oder low > min(o,c,h))")

    # Unplausible Preisspruenge
    returns_pct = df["close"].pct_change().abs() * 100
    spikes = returns_pct[returns_pct > max_single_bar_move_pct]
    if len(spikes) > 0:
        issues.append(
            f"{len(spikes)} Kerzen mit Preisaenderung > {max_single_bar_move_pct}% "
            f"(groesste: {spikes.max():.1f}% bei {spikes.idxmax()})"
        )

    # Volumen
    if "volume" in df.columns:
        neg_vol = int((df["volume"] < 0).sum())
        zero_vol = int((df["volume"] == 0).sum())
        if neg_vol > 0:
            issues.append(f"{neg_vol} Kerzen mit negativem Volumen")
        if zero_vol > len(df) * 0.1:
            issues.append(f"{zero_vol} von {len(df)} Kerzen mit Volumen = 0 (>10%, evtl. inaktives Instrument)")

    return {
        "is_valid": len(issues) == 0,
        "issues": issues,
        "row_count": len(df),
        "date_range": (str(df.index.min()), str(df.index.max())) if isinstance(df.index, pd.DatetimeIndex) else None,
    }


def clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """
    Minimal-invasive Bereinigung: entfernt doppelte Zeitstempel (erste Kerze
    behalten), sortiert aufsteigend, entfernt Zeilen mit NaN in OHLC.
    Aendert NICHT die Werte selbst (kein Fuellen/Interpolieren) -- das
    entscheidet der Aufrufer bewusst, damit RL-Training keine kuenstlichen
    Kerzen als reale Marktbewegung lernt.
    """
    out = df.copy()
    if isinstance(out.index, pd.DatetimeIndex):
        out = out[~out.index.duplicated(keep="first")].sort_index()
    out = out.dropna(subset=["open", "high", "low", "close"])
    return out
