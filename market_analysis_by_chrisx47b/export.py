"""
Export-Utilities: CSV fuer OHLCV-DataFrames, generischer Text-Export (z.B.
fuer generierten Pine-Script-Code).

Bewusst generisch gebaut -- export_ohlcv_csv funktioniert mit jedem
DataFrame aus indicators.py/rl_features.py/mt5_source.py etc.,
export_text_file mit jedem String-Inhalt (Pine Script, Reports, Logs).

WICHTIG zum Speicherort: Dieser MCP-Server laeuft lokal auf deinem Rechner
(bei MT5 sogar zwingend). Jede Datei landet direkt auf deiner Festplatte --
es gibt keinen Upload/Download-Schritt wie in einer Cloud-Sandbox. Ohne
eigenen `filepath` wird automatisch ein Dateiname im aktuellen
Arbeitsverzeichnis des Server-Prozesses erzeugt.
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


def export_text_file(content: str, filepath: str | None = None,
                      base_name: str | None = None, extension: str = "txt") -> dict:
    """Schreibt beliebigen Textinhalt (z.B. generierten Pine-Script-Code) in
    eine Datei. Ohne `filepath` wird automatisch ein Dateiname aus
    `base_name`/Zeitstempel gebaut. Gibt Metadaten zurueck (Pfad, Zeilenzahl,
    Groesse), NICHT nochmal den Inhalt -- der steht ja schon in der Antwort.
    """
    if not content:
        raise ValueError("content ist leer -- nichts zu exportieren.")

    if filepath is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name_parts = [p for p in (base_name, ts) if p]
        filename = "_".join(str(p) for p in name_parts) + f".{extension}"
        filepath = os.path.join(os.getcwd(), filename)

    filepath = os.path.abspath(filepath)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "filepath": filepath,
        "line_count": len(content.splitlines()),
        "file_size_kb": round(os.path.getsize(filepath) / 1024, 1),
    }
