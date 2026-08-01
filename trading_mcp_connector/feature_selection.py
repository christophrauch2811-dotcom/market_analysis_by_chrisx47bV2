"""
Reduziert Redundanz im 210-Feature-Vektor:

1. correlation_report() -- berechnet paarweise Korrelationen ueber eine
   Historie echter Daten und schlaegt Features vor, die man streichen
   koennte (bei |r| > threshold wird jeweils nur eines der beiden behalten).
   Erfordert echte historische Daten -- eine sinnvolle Kuerzung laesst sich
   nicht aus synthetischen Zufallsdaten ableiten.

2. CORE_FEATURE_SET -- eine von Hand kuratierte, deutlich kleinere Auswahl
   (~45 statt 210 Features), die die Kategorien mit wenig Ueberlappung
   abdeckt (z.B. nur RSI-14 statt RSI-7/14/21, nur eine ATR-Basis).
   Nuetzlich als Startpunkt, wenn 210 Inputs fuers erste Training zu viel sind.
"""

from __future__ import annotations
import pandas as pd


def correlation_report(feature_history: pd.DataFrame, threshold: float = 0.95) -> dict:
    """
    feature_history: DataFrame, bei dem jede Zeile ein Zeitpunkt ist und jede
    Spalte ein Feature (z.B. durch wiederholten Aufruf von build_model_feature_vector
    ueber eine historische Zeitreihe erzeugt). Nur numerische Spalten fliessen ein.

    Gibt Paare stark korrelierter Features zurueck (|r| > threshold) plus einen
    Vorschlag, welches der beiden man behalten wuerde (das mit dem kuerzeren,
    'einfacheren' Namen -- grobe Heuristik, letzte Entscheidung bleibt beim Menschen).
    """
    numeric = feature_history.select_dtypes(include="number").dropna(axis=1, how="all")
    if numeric.shape[1] < 2 or numeric.shape[0] < 10:
        return {"pairs": [], "note": "Zu wenig Daten/Spalten fuer eine sinnvolle Korrelationsanalyse."}

    corr = numeric.corr().abs()
    pairs = []
    seen = set()
    for col in corr.columns:
        for row in corr.index:
            if col == row or (row, col) in seen or (col, row) in seen:
                continue
            seen.add((col, row))
            r = corr.loc[row, col]
            if pd.notna(r) and r > threshold:
                keep = row if len(row) <= len(col) else col
                drop = col if keep == row else row
                pairs.append({"feature_a": row, "feature_b": col, "correlation": round(float(r), 4),
                              "suggested_keep": keep, "suggested_drop": drop})

    pairs.sort(key=lambda p: -p["correlation"])
    drop_candidates = sorted({p["suggested_drop"] for p in pairs})
    return {
        "pairs": pairs,
        "drop_candidates": drop_candidates,
        "note": (f"{len(drop_candidates)} von {numeric.shape[1]} Features sind mit mind. einem anderen "
                 f"Feature ueber {threshold} korreliert. Vorschlag ist eine Heuristik -- "
                 f"fachliche Pruefung vor dem Streichen empfohlen."),
    }


# Handkuratierte, deutlich schlankere Auswahl (~45 Features) als Startpunkt,
# wenn 210 Inputs fuer ein erstes Training zu viel Rauschen/Overfitting-Risiko sind.
CORE_FEATURE_SET = [
    # Preis/Returns
    "return_1", "return_5", "return_20", "log_return_5",
    # Trend (je ein Vertreter pro Zeithorizont statt aller Varianten)
    "price_vs_sma_20_pct", "price_vs_sma_50_pct", "price_vs_sma_200_pct",
    "macd_bull_cross", "adx_14", "di_diff", "price_above_cloud", "price_above_psar",
    # Momentum (nur RSI-14 statt 7/14/21)
    "rsi_14", "stoch_k", "williams_r", "roc_10", "cci_14",
    # Volatilitaet
    "atr_pct_of_price", "bb_width_pct", "bb_percent_b", "realized_vol_20",
    # Volumen
    "volume_zscore_20", "price_vs_vwap_pct", "mfi_14", "cmf_20",
    # Breakout (nur 20er-Fenster statt 20/50/100)
    "breakout_up_20", "breakout_down_20", "distance_to_high_20_pct", "distance_to_low_20_pct",
    "range_expansion_ratio", "new_high_100", "new_low_100",
    # Pivots/Fibonacci (nur die wichtigsten Distanzen)
    "distance_to_pivot_pct", "distance_to_fib_618_pct", "in_golden_zone",
    # Candlestick (nur die haeufigsten Muster)
    "is_doji", "is_hammer", "is_bullish_engulfing", "is_bearish_engulfing", "gap_up", "gap_down",
    # Stop-Loss/Risiko
    "distance_to_atr_stop_long_pct", "distance_to_swing_low_stop_pct",
    # Session
    "hour_of_day", "is_london_session", "is_ny_session",
    # Statistik
    "zscore_price_20", "skewness_20",
    # Regime (die aussagekraeftigsten statt aller Rohwerte)
    "regime_adx_14", "regime_choppiness_index", "regime_hurst_exponent",
    "regime_direction_up", "regime_direction_down", "regime_structure_bullish",
    "regime_structure_bearish", "regime_volatility_high",
    # Positions-State
    "position_side_long", "position_side_short", "unrealized_pnl_pct",
    "distance_to_stop_loss_pct", "equity_drawdown_pct",
]


def build_core_feature_vector(full_model_vector: dict) -> dict:
    """Filtert einen bereits berechneten build_model_feature_vector()-Output
    auf CORE_FEATURE_SET. Fehlende Keys werden stillschweigend ausgelassen
    (z.B. falls das Schema sich seither veraendert hat)."""
    return {k: full_model_vector[k] for k in CORE_FEATURE_SET if k in full_model_vector}
