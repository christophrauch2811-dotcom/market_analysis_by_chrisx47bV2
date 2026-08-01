"""
CSV-Export fuer OHLCV-DataFrames.

Bewusst als generische Utility gebaut (nicht MT5-spezifisch), auch wenn der
erste Anwendungsfall MT5-Historie ist -- funktioniert mit jedem DataFrame
aus indicators.py/rl_features.py/mt5_source.py etc.

WICHTIG zum Speicherort: Da MT5 nur lokal auf deinem Windows-Rechner laeuft
(dort, wo dieser MCP-Server gestartet wird), landet die CSV-Datei direkt auf
deiner Festplatte -- es gibt keinen Upload/Download-Schritt wie in einer
Cloud-Sandbox. Ohne eigenen `filepath` wird die Datei im aktuellen
Arbeitsverzeichnis des Server-Prozesses abgelegt.
"""

from __future__ import annotations
import os
from datetime import datetime

import pandas as pd


def export_ohlcv_csv(df: pd.DataFrame, filepath: str | None = None,
                      symbol: str | None = None, timeframe: str | None = None) -> dict:
    """Schreibt `df` als CSV. Ohne `filepath` wird automatisch ein Dateiname
    aus Symbol/Timeframe/Zeitstempel gebaut. Gibt Metadaten zurueck (Pfad,
    Zeilenzahl, Datumsspanne), NICHT den Datei-Inhalt -- bei mehreren Jahren
    Historie waere das zu viel fuer eine Chat-Antwort.
    """
    if df.empty:
        raise ValueError("DataFrame ist leer -- nichts zu exportieren.")

    if filepath is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name_parts = [p for p in (symbol, timeframe, ts) if p]
        filename = "_".join(str(p) for p in name_parts) + ".csv"
        filepath = os.path.join(os.getcwd(), filename)

    filepath = os.path.abspath(filepath)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    df.to_csv(filepath)

    return {
        "filepath": filepath,
        "row_count": len(df),
        "columns": list(df.columns),
        "date_range": (str(df.index.min()), str(df.index.max())) if isinstance(df.index, pd.DatetimeIndex) else None,
        "file_size_kb": round(os.path.getsize(filepath) / 1024, 1),
    }
