"""
Breite Indikator-Bibliothek auf Basis von OHLCV-Daten (pandas DataFrame).
Nutzt die 'ta'-Bibliothek fuer Standardindikatoren + eigene Fibonacci-Funktion.

Erwartetes DataFrame-Format (Spalten): open, high, low, close, volume
Index: Zeitstempel (aufsteigend sortiert)
"""

from __future__ import annotations
import pandas as pd
import ta


def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Berechnet einen breiten Satz an Trend-, Momentum-, Volatilitaets- und
    Volumen-Indikatoren und haengt sie als neue Spalten an das DataFrame an.
    """
    df = df.copy()

    # --- Trend ---
    df["sma_20"] = ta.trend.sma_indicator(df["close"], window=20)
    df["sma_50"] = ta.trend.sma_indicator(df["close"], window=50)
    df["sma_200"] = ta.trend.sma_indicator(df["close"], window=200)
    df["ema_12"] = ta.trend.ema_indicator(df["close"], window=12)
    df["ema_26"] = ta.trend.ema_indicator(df["close"], window=26)
    macd = ta.trend.MACD(df["close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_diff"] = macd.macd_diff()
    df["adx"] = ta.trend.adx(df["high"], df["low"], df["close"])
    df["cci"] = ta.trend.cci(df["high"], df["low"], df["close"])
    ichimoku = ta.trend.IchimokuIndicator(df["high"], df["low"])
    df["ichimoku_a"] = ichimoku.ichimoku_a()
    df["ichimoku_b"] = ichimoku.ichimoku_b()
    psar = ta.trend.PSARIndicator(df["high"], df["low"], df["close"])
    df["psar"] = psar.psar()

    # --- Momentum ---
    df["rsi_14"] = ta.momentum.rsi(df["close"], window=14)
    stoch = ta.momentum.StochasticOscillator(df["high"], df["low"], df["close"])
    df["stoch_k"] = stoch.stoch()
    df["stoch_d"] = stoch.stoch_signal()
    df["williams_r"] = ta.momentum.williams_r(df["high"], df["low"], df["close"])
    df["roc"] = ta.momentum.roc(df["close"])

    # --- Volatilitaet ---
    bb = ta.volatility.BollingerBands(df["close"])
    df["bb_high"] = bb.bollinger_hband()
    df["bb_low"] = bb.bollinger_lband()
    df["bb_mid"] = bb.bollinger_mavg()
    df["atr"] = ta.volatility.average_true_range(df["high"], df["low"], df["close"])
    df["keltner_high"] = ta.volatility.keltner_channel_hband(df["high"], df["low"], df["close"])
    df["keltner_low"] = ta.volatility.keltner_channel_lband(df["high"], df["low"], df["close"])

    # --- Volumen ---
    if "volume" in df.columns:
        df["obv"] = ta.volume.on_balance_volume(df["close"], df["volume"])
        df["vwap"] = ta.volume.volume_weighted_average_price(
            df["high"], df["low"], df["close"], df["volume"]
        )
        df["mfi"] = ta.volume.money_flow_index(
            df["high"], df["low"], df["close"], df["volume"]
        )

    return df


def fibonacci_retracement(df: pd.DataFrame, lookback: int = 100) -> dict:
    """
    Berechnet Fibonacci-Retracement-Level ueber die letzten `lookback` Kerzen.
    Gibt die Standard-Level 0/23.6/38.2/50/61.8/78.6/100 % zurueck,
    sowohl fuer einen Aufwaerts- als auch Abwaertstrend.
    """
    window = df.tail(lookback)
    high = window["high"].max()
    low = window["low"].min()
    diff = high - low

    levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    uptrend = {f"{int(l*1000)/10}%": round(high - diff * l, 5) for l in levels}
    downtrend = {f"{int(l*1000)/10}%": round(low + diff * l, 5) for l in levels}

    return {
        "swing_high": high,
        "swing_low": low,
        "uptrend_retracement": uptrend,
        "downtrend_retracement": downtrend,
    }


def latest_snapshot(df: pd.DataFrame) -> dict:
    """Gibt nur die letzte Zeile aller berechneten Indikatoren als dict zurueck."""
    enriched = compute_all_indicators(df)
    last = enriched.iloc[-1]
    return {k: (None if pd.isna(v) else round(float(v), 6) if isinstance(v, (int, float)) else v)
            for k, v in last.items()}
