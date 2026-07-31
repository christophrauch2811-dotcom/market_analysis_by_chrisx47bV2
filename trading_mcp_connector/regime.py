"""
Regime- und Trenderkennung -- bewusst als eigenstaendiges Modul ohne
Abhaengigkeit zu rl_features.py oder einer bestimmten Datenquelle gebaut,
damit es 1:1 in jeden zukuenftigen Connector importiert werden kann:

    from regime import detect_regime
    regime = detect_regime(df)   # df = beliebiges OHLCV-DataFrame

Erkennt:
  - Trendrichtung & -staerke (ADX, lineare Regression, MA-Alignment)
  - Marktstruktur (Higher-Highs/Higher-Lows vs. Lower-Highs/Lower-Lows)
  - Mean-Reversion vs. Trending-Charakter (Hurst-Exponent, Choppiness Index)
  - Volatilitaetsregime (niedrig/normal/hoch, Bollinger-Squeeze)
  - Ein zusammenfassendes Regime-Label fuer schnelle Entscheidungen
"""

from __future__ import annotations
import numpy as np
import pandas as pd
import ta


# ---------------------------------------------------------------------------
# Bausteine
# ---------------------------------------------------------------------------

def linear_regression_trend(series: pd.Series, window: int = 50) -> dict:
    """Steigung + R^2 einer linearen Regression der letzten `window` Werte.
    Normalisierte Steigung (% pro Bar relativ zum Preisniveau) macht Werte
    ueber verschiedene Instrumente/Timeframes vergleichbar.
    """
    y = series.tail(window).values
    x = np.arange(len(y))
    if len(y) < 5 or np.all(y == y[0]):
        return {"slope_pct_per_bar": 0.0, "r_squared": 0.0}
    slope, intercept = np.polyfit(x, y, 1)
    y_pred = slope * x + intercept
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    slope_pct = slope / y.mean() if y.mean() else 0.0
    return {"slope_pct_per_bar": float(slope_pct), "r_squared": float(r_squared)}


def choppiness_index(df: pd.DataFrame, window: int = 14) -> float:
    """0-100. >61.8 = Seitwaertsmarkt/choppy, <38.2 = klarer Trend."""
    atr_sum = ta.volatility.average_true_range(df["high"], df["low"], df["close"], window=1).rolling(window).sum()
    high_low_range = df["high"].rolling(window).max() - df["low"].rolling(window).min()
    chop = 100 * np.log10(atr_sum / high_low_range) / np.log10(window)
    val = chop.iloc[-1]
    return float(val) if pd.notna(val) else 50.0


def hurst_exponent(series: pd.Series, max_lag: int = 20) -> float:
    """Approximation ueber Rescaled-Range-Methode.
    ~0.5 = Random Walk, >0.5 = trending/persistent, <0.5 = mean-reverting.
    """
    ts = series.tail(200).values
    if len(ts) < max_lag * 2:
        return 0.5
    lags = range(2, max_lag)
    tau = [np.std(np.subtract(ts[lag:], ts[:-lag])) for lag in lags]
    tau = [t if t > 0 else 1e-8 for t in tau]
    poly = np.polyfit(np.log(list(lags)), np.log(tau), 1)
    return float(poly[0] * 2.0)


def ma_alignment(df: pd.DataFrame) -> dict:
    """Prueft, ob kurz-/mittel-/langfristige MAs in Trendrichtung gestapelt sind
    (klassisches 'Perfect Order'-Konzept).
    """
    c = df["close"]
    sma20 = ta.trend.sma_indicator(c, 20).iloc[-1]
    sma50 = ta.trend.sma_indicator(c, 50).iloc[-1]
    sma200 = ta.trend.sma_indicator(c, 200).iloc[-1] if len(df) >= 200 else sma50
    price = c.iloc[-1]

    bullish_order = price > sma20 > sma50 > sma200
    bearish_order = price < sma20 < sma50 < sma200
    score = sum([price > sma20, sma20 > sma50, sma50 > sma200]) - sum(
        [price < sma20, sma20 < sma50, sma50 < sma200]
    )
    return {
        "bullish_perfect_order": bool(bullish_order),
        "bearish_perfect_order": bool(bearish_order),
        "alignment_score": int(score),  # -3 (voll bearish) .. +3 (voll bullish)
    }


def market_structure(df: pd.DataFrame, lookback: int = 50, swing_window: int = 5) -> dict:
    """Erkennt Higher-Highs/Higher-Lows (Aufwaertsstruktur) vs.
    Lower-Highs/Lower-Lows (Abwaertsstruktur) ueber lokale Swing-Punkte.
    """
    window = df.tail(lookback)
    highs, lows = window["high"], window["low"]

    swing_highs, swing_lows = [], []
    for i in range(swing_window, len(window) - swing_window):
        seg_h = highs.iloc[i - swing_window: i + swing_window + 1]
        seg_l = lows.iloc[i - swing_window: i + swing_window + 1]
        if highs.iloc[i] == seg_h.max():
            swing_highs.append(highs.iloc[i])
        if lows.iloc[i] == seg_l.min():
            swing_lows.append(lows.iloc[i])

    hh = len(swing_highs) >= 2 and swing_highs[-1] > swing_highs[-2]
    hl = len(swing_lows) >= 2 and swing_lows[-1] > swing_lows[-2]
    lh = len(swing_highs) >= 2 and swing_highs[-1] < swing_highs[-2]
    ll = len(swing_lows) >= 2 and swing_lows[-1] < swing_lows[-2]

    if hh and hl:
        structure = "higher_highs_higher_lows"
    elif lh and ll:
        structure = "lower_highs_lower_lows"
    else:
        structure = "mixed"

    return {
        "market_structure": structure,
        "swing_high_count": len(swing_highs),
        "swing_low_count": len(swing_lows),
    }


def volatility_regime(df: pd.DataFrame, window: int = 20, lookback: int = 200) -> dict:
    """Stuft die aktuelle Volatilitaet relativ zu ihrer eigenen Historie ein
    (Perzentil-basiert -- funktioniert instrumentuebergreifend ohne feste Schwellen).
    """
    atr = ta.volatility.average_true_range(df["high"], df["low"], df["close"], window=14)
    atr_pct = (atr / df["close"]).dropna()
    current = atr_pct.iloc[-1]
    history = atr_pct.tail(lookback)
    percentile = (history < current).mean() if len(history) > 1 else 0.5

    if percentile > 0.8:
        label = "high"
    elif percentile < 0.2:
        label = "low"
    else:
        label = "normal"

    bb = ta.volatility.BollingerBands(df["close"])
    bb_width = (bb.bollinger_hband() - bb.bollinger_lband()) / bb.bollinger_mavg()
    squeeze = bool(bb_width.iloc[-1] < bb_width.tail(lookback).quantile(0.2))

    return {
        "volatility_regime": label,
        "volatility_percentile": float(percentile),
        "bollinger_squeeze": squeeze,
    }


# ---------------------------------------------------------------------------
# Zusammenfassung
# ---------------------------------------------------------------------------

def detect_regime(df: pd.DataFrame) -> dict:
    """
    Baut ein zusammenfassendes Regime-Objekt fuer ein beliebiges OHLCV-DataFrame.
    Gedacht als gemeinsame Basis, die jeder Connector (aktueller wie zukuenftige)
    gleich aufrufen kann -- unabhaengig davon, woher die Kerzen kommen.
    """
    assert len(df) >= 60, "Mindestens 60 Kerzen fuer sinnvolle Regime-Erkennung empfohlen"

    c = df["close"]
    adx = ta.trend.adx(df["high"], df["low"], c, window=14)
    adx_val = float(adx.iloc[-1]) if pd.notna(adx.iloc[-1]) else 0.0

    reg = linear_regression_trend(c)
    chop = choppiness_index(df)
    hurst = hurst_exponent(c)
    align = ma_alignment(df)
    structure = market_structure(df)
    vol = volatility_regime(df)

    # Trendrichtung aus Regressions-Steigung + MA-Alignment
    if reg["slope_pct_per_bar"] > 0 and align["alignment_score"] >= 1:
        direction = "up"
    elif reg["slope_pct_per_bar"] < 0 and align["alignment_score"] <= -1:
        direction = "down"
    else:
        direction = "sideways"

    # Trendstaerke-Bucket aus ADX (Standard-Trading-Konvention)
    if adx_val >= 25:
        strength = "strong"
    elif adx_val >= 15:
        strength = "weak"
    else:
        strength = "none"

    # Zusammenfassendes Label fuer schnelle Entscheidungen/Filter
    if strength == "strong" and direction != "sideways":
        regime_label = f"strong_trend_{direction}"
    elif strength == "weak" and direction != "sideways":
        regime_label = f"weak_trend_{direction}"
    elif chop > 61.8 or hurst < 0.45:
        regime_label = "ranging_mean_reverting"
    else:
        regime_label = "undefined"

    return {
        "regime_label": regime_label,
        "trend_direction": direction,
        "trend_strength": strength,
        "adx_14": adx_val,
        "regression_slope_pct_per_bar": reg["slope_pct_per_bar"],
        "regression_r_squared": reg["r_squared"],
        "choppiness_index": chop,
        "hurst_exponent": hurst,
        "is_trending_persistent": hurst > 0.55,
        "is_mean_reverting": hurst < 0.45,
        **align,
        **structure,
        **vol,
    }
