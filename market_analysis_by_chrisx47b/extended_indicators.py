"""
Erweiterte Indikatoren -- schliesst die Luecke zwischen unserem urspruenglichen
Indikator-Satz und TradingViews Liste eingebauter technischer Indikatoren
(https://www.tradingview.com/support/folders/43000587405-built-in-indicators/,
~150 echte Preis-/Volumen-Indikatoren nach Abzug von On-Chain-Metriken,
Fundamentaldaten, ETF-Flows etc.).

Bewusst NICHT abgedeckt (Begruendung):
  - Chande Kroll Stop, Klinger Oscillator, McGinley Dynamic, SMI Ergodic,
    DEMA/TEMA, Woodies CCI, Rob Booker-Indikatoren, Zig Zag, Williams Fractal:
    Nische/selten genutzt oder inhaltlich redundant mit bereits vorhandener
    Swing-Erkennung (chart_patterns.py) bzw. den Standard-EMA/ATR-Varianten.
  - Die 100.000+ Community-Pine-Scripts: kein fester Standard, kein
    endliches, sinnvolles Ziel (siehe Diskussion im Chat).

Wo moeglich ueber die 'ta'-Bibliothek (TRIX, KST, DPO, Vortex, PPO, PVO,
StochRSI, ADL, Ease of Movement, NVI, PVT, Mass Index -- alle bereits in
'ta' implementiert, nur bisher nicht angebunden). Fuer alles, was 'ta' nicht
bietet (Supertrend, Hull MA, VWMA, Chande Momentum Oscillator, Connors RSI,
Fisher Transform, Williams Alligator, Chaikin Oscillator), Standardformeln
selbst implementiert.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
import ta


# ---------------------------------------------------------------------------
# Aus der 'ta'-Bibliothek (nur anbinden, nicht neu erfinden)
# ---------------------------------------------------------------------------

def _ta_library_indicators(df: pd.DataFrame) -> dict:
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]
    f = {}

    f["trix_15"] = ta.trend.trix(c, window=15).iloc[-1]
    f["kst"] = ta.trend.kst(c).iloc[-1]
    f["kst_signal"] = ta.trend.kst_sig(c).iloc[-1]
    f["dpo"] = ta.trend.dpo(c).iloc[-1]  # absolut (Preis - verschobener SMA)
    f["mass_index"] = ta.trend.mass_index(h, l).iloc[-1]

    vortex_pos = ta.trend.vortex_indicator_pos(h, l, c)
    vortex_neg = ta.trend.vortex_indicator_neg(h, l, c)
    f["vortex_pos"] = vortex_pos.iloc[-1]
    f["vortex_neg"] = vortex_neg.iloc[-1]
    f["vortex_diff"] = f["vortex_pos"] - f["vortex_neg"]

    f["ppo"] = ta.momentum.ppo(c).iloc[-1]
    f["ppo_signal"] = ta.momentum.ppo_signal(c).iloc[-1]
    f["ppo_hist"] = ta.momentum.ppo_hist(c).iloc[-1]
    f["pvo"] = ta.momentum.pvo(v).iloc[-1]
    f["pvo_signal"] = ta.momentum.pvo_signal(v).iloc[-1]
    f["pvo_hist"] = ta.momentum.pvo_hist(v).iloc[-1]

    f["stochrsi"] = ta.momentum.stochrsi(c).iloc[-1]
    f["stochrsi_k"] = ta.momentum.stochrsi_k(c).iloc[-1]
    f["stochrsi_d"] = ta.momentum.stochrsi_d(c).iloc[-1]

    f["adl"] = ta.volume.acc_dist_index(h, l, c, v).iloc[-1]  # absolut/kumulativ
    f["eom"] = ta.volume.ease_of_movement(h, l, v).iloc[-1]
    f["nvi"] = ta.volume.negative_volume_index(c, v).iloc[-1]  # absolut/Index
    f["pvt"] = ta.volume.volume_price_trend(c, v).iloc[-1]  # absolut/kumulativ

    return f


# ---------------------------------------------------------------------------
# Selbst implementiert (in 'ta' nicht enthalten, aber TradingView-Standardformeln)
# ---------------------------------------------------------------------------

def _wma(series: pd.Series, window: int) -> pd.Series:
    weights = np.arange(1, window + 1)
    return series.rolling(window).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)


def hull_moving_average(close: pd.Series, window: int = 9) -> pd.Series:
    half = max(1, window // 2)
    sqrt_n = max(1, int(round(np.sqrt(window))))
    wma_half = _wma(close, half)
    wma_full = _wma(close, window)
    raw_hma = 2 * wma_half - wma_full
    return _wma(raw_hma, sqrt_n)


def vwma(df: pd.DataFrame, window: int = 20) -> pd.Series:
    pv = df["close"] * df["volume"]
    return pv.rolling(window).sum() / df["volume"].rolling(window).sum()


def chande_momentum_oscillator(close: pd.Series, window: int = 14) -> pd.Series:
    diff = close.diff()
    up = diff.clip(lower=0).rolling(window).sum()
    down = (-diff.clip(upper=0)).rolling(window).sum()
    return 100 * (up - down) / (up + down).replace(0, np.nan)


def chaikin_oscillator(df: pd.DataFrame) -> pd.Series:
    adl = ta.volume.acc_dist_index(df["high"], df["low"], df["close"], df["volume"])
    return adl.ewm(span=3, adjust=False).mean() - adl.ewm(span=10, adjust=False).mean()


def supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> dict:
    """Klassischer Supertrend-Algorithmus (iterativ, Standardformel).
    Gibt die aktuelle Linie + Richtung (1 = Aufwaertstrend/Preis oberhalb,
    -1 = Abwaertstrend/Preis unterhalb) zurueck.
    """
    hl2 = (df["high"] + df["low"]) / 2
    atr = ta.volatility.average_true_range(df["high"], df["low"], df["close"], window=period)
    basic_upper = (hl2 + multiplier * atr).values
    basic_lower = (hl2 - multiplier * atr).values
    close = df["close"].values
    n = len(df)

    final_upper = np.zeros(n)
    final_lower = np.zeros(n)
    st = np.zeros(n)
    final_upper[0] = basic_upper[0]
    final_lower[0] = basic_lower[0]
    st[0] = basic_upper[0]

    for i in range(1, n):
        final_upper[i] = (basic_upper[i] if (basic_upper[i] < final_upper[i - 1] or close[i - 1] > final_upper[i - 1])
                           else final_upper[i - 1])
        final_lower[i] = (basic_lower[i] if (basic_lower[i] > final_lower[i - 1] or close[i - 1] < final_lower[i - 1])
                           else final_lower[i - 1])
        if st[i - 1] == final_upper[i - 1]:
            st[i] = final_upper[i] if close[i] <= final_upper[i] else final_lower[i]
        else:
            st[i] = final_lower[i] if close[i] >= final_lower[i] else final_upper[i]

    direction = 1 if st[-1] == final_lower[-1] else -1
    return {"value": float(st[-1]), "direction": direction}


def williams_alligator(df: pd.DataFrame) -> dict:
    """Jaw/Teeth/Lips als SMMA (Wilder-Glaettung) auf hl2, ohne den visuellen
    Forward-Shift (der ist nur Darstellung, keine Rechenlogik) -- fuer
    Feature-Zwecke reicht der aktuelle glatte Wert je Linie.
    """
    hl2 = (df["high"] + df["low"]) / 2

    def smma(series: pd.Series, window: int) -> pd.Series:
        out = series.rolling(window).mean()
        result = out.copy()
        for i in range(window, len(series)):
            prev = result.iloc[i - 1] if pd.notna(result.iloc[i - 1]) else out.iloc[i]
            result.iloc[i] = (prev * (window - 1) + series.iloc[i]) / window
        return result

    jaw = smma(hl2, 13).iloc[-1]
    teeth = smma(hl2, 8).iloc[-1]
    lips = smma(hl2, 5).iloc[-1]
    return {"jaw": float(jaw), "teeth": float(teeth), "lips": float(lips)}


def fisher_transform(df: pd.DataFrame, window: int = 9) -> dict:
    h, l = df["high"], df["low"]
    hl2 = (h + l) / 2
    max_h = hl2.rolling(window).max()
    min_l = hl2.rolling(window).min()
    raw = (hl2 - min_l) / (max_h - min_l).replace(0, np.nan) - 0.5

    value = np.zeros(len(df))
    fish = np.zeros(len(df))
    for i in range(1, len(df)):
        v = 0.33 * 2 * raw.iloc[i] + 0.67 * value[i - 1] if pd.notna(raw.iloc[i]) else value[i - 1]
        value[i] = min(max(v, -0.999), 0.999)
        fish[i] = 0.5 * np.log((1 + value[i]) / (1 - value[i])) + 0.5 * fish[i - 1]

    return {"fisher": float(fish[-1]), "fisher_signal": float(fish[-2]) if len(fish) > 1 else float(fish[-1])}


def connors_rsi(close: pd.Series, rsi_period: int = 3, streak_period: int = 2, rank_period: int = 100) -> float:
    """CRSI = (RSI(close, 3) + RSI(Streak, 2) + PercentRank(1-Tages-Return, 100)) / 3"""
    rsi_close = ta.momentum.rsi(close, window=rsi_period)

    diff = close.diff()
    streak = pd.Series(0, index=close.index, dtype=float)
    cur = 0
    for i in range(1, len(close)):
        if diff.iloc[i] > 0:
            cur = cur + 1 if cur >= 0 else 1
        elif diff.iloc[i] < 0:
            cur = cur - 1 if cur <= 0 else -1
        else:
            cur = 0
        streak.iloc[i] = cur
    rsi_streak = ta.momentum.rsi(streak, window=streak_period)

    roc1 = close.pct_change()
    percent_rank = roc1.rolling(rank_period).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False) * 100

    crsi = (rsi_close.iloc[-1] + rsi_streak.iloc[-1] + percent_rank.iloc[-1]) / 3
    return float(crsi) if pd.notna(crsi) else float("nan")


# ---------------------------------------------------------------------------
# Zusammenfuehrung
# ---------------------------------------------------------------------------

def compute_extended_indicators(df: pd.DataFrame) -> dict:
    """Baut alle erweiterten Indikatoren fuer den letzten Zeitpunkt in `df`."""
    assert len(df) >= 110, "Mindestens 110 Kerzen empfohlen (Connors RSI braucht 100er Rank-Fenster)"

    f = {}
    f.update(_ta_library_indicators(df))

    close = df["close"]
    hull = hull_moving_average(close).iloc[-1]
    vwma_val = vwma(df).iloc[-1]
    f["hull_ma_9"] = float(hull)
    f["vwma_20"] = float(vwma_val)
    f["price_vs_hull_pct"] = float((close.iloc[-1] - hull) / hull) if hull else np.nan
    f["price_vs_vwma_pct"] = float((close.iloc[-1] - vwma_val) / vwma_val) if vwma_val else np.nan

    f["cmo_14"] = float(chande_momentum_oscillator(close).iloc[-1])
    f["chaikin_oscillator"] = float(chaikin_oscillator(df).iloc[-1])

    st = supertrend(df)
    f["supertrend_value"] = st["value"]
    f["supertrend_direction"] = st["direction"]
    f["price_vs_supertrend_pct"] = float((close.iloc[-1] - st["value"]) / st["value"]) if st["value"] else np.nan

    alligator = williams_alligator(df)
    f["alligator_jaw"] = alligator["jaw"]
    f["alligator_teeth"] = alligator["teeth"]
    f["alligator_lips"] = alligator["lips"]
    f["alligator_lips_above_teeth"] = int(alligator["lips"] > alligator["teeth"])
    f["alligator_teeth_above_jaw"] = int(alligator["teeth"] > alligator["jaw"])
    f["alligator_spread_pct"] = float((alligator["lips"] - alligator["jaw"]) / alligator["jaw"]) if alligator["jaw"] else np.nan

    fisher = fisher_transform(df)
    f["fisher_transform"] = fisher["fisher"]
    f["fisher_transform_signal"] = fisher["fisher_signal"]

    f["connors_rsi"] = connors_rsi(close)

    return f
