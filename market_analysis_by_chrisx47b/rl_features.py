"""
Breite Feature-Bibliothek fuer RL-Trading-Agenten.

Liefert einen flachen dict mit 100+ Features je Zeitpunkt, gruppiert in:
  1. Preis/Returns
  2. Trend/Moving Averages
  3. Momentum
  4. Volatilitaet
  5. Volumen
  6. Breakout-Erkennung
  7. Support/Resistance & Pivots
  8. Fibonacci
  9. Candlestick-Patterns
  10. Stop-Loss / Risikomanagement
  11. Session/Zeit
  12. Statistik
  13. Positions-State (nur wenn der RL-Agent gerade eine Position haelt)

Erwartetes DataFrame-Format: Spalten open, high, low, close, volume,
DatetimeIndex, aufsteigend sortiert. Fuer sinnvolle Werte werden
mindestens ~250 Kerzen Historie empfohlen (wegen sma_200 etc.).
"""

from __future__ import annotations
import hashlib
import numpy as np
import pandas as pd
import ta
from . import regime as regime_mod
from . import extended_indicators as ext_mod


def _safe(x):
    """NaN/Inf -> None, numpy -> nativer Python-Typ (fuer JSON-Ausgabe)."""
    if x is None:
        return None
    try:
        if isinstance(x, (np.floating, np.integer)):
            x = x.item()
        if isinstance(x, float) and (np.isnan(x) or np.isinf(x)):
            return None
        if isinstance(x, (int, float, bool, str)):
            return round(x, 6) if isinstance(x, float) else x
        return x
    except Exception:
        return None


def _pct_diff(a, b):
    if b == 0 or pd.isna(b):
        return np.nan
    return (a - b) / b


# ---------------------------------------------------------------------------
# 1. Preis / Returns
# ---------------------------------------------------------------------------

def _price_features(df: pd.DataFrame) -> dict:
    c = df["close"]
    f = {}
    for n in (1, 3, 5, 10, 20):
        f[f"return_{n}"] = c.pct_change(n).iloc[-1]
        f[f"log_return_{n}"] = np.log(c / c.shift(n)).iloc[-1]
    f["overnight_gap_pct"] = _pct_diff(df["open"].iloc[-1], c.iloc[-2])
    f["body_range_pct"] = _pct_diff(c.iloc[-1], df["open"].iloc[-1])
    f["high_low_range_pct"] = _pct_diff(df["high"].iloc[-1], df["low"].iloc[-1])
    f["close_position_in_range"] = (
        (c.iloc[-1] - df["low"].iloc[-1]) / (df["high"].iloc[-1] - df["low"].iloc[-1])
        if df["high"].iloc[-1] != df["low"].iloc[-1] else 0.5
    )
    return f


# ---------------------------------------------------------------------------
# 2. Trend / Moving Averages
# ---------------------------------------------------------------------------

def _trend_features(df: pd.DataFrame) -> dict:
    c = df["close"]
    f = {}
    for n in (10, 20, 50, 100, 200):
        sma = ta.trend.sma_indicator(c, window=n)
        f[f"sma_{n}"] = sma.iloc[-1]
        f[f"price_vs_sma_{n}_pct"] = _pct_diff(c.iloc[-1], sma.iloc[-1])
    for n in (9, 21, 50, 200):
        ema = ta.trend.ema_indicator(c, window=n)
        f[f"ema_{n}"] = ema.iloc[-1]
        f[f"price_vs_ema_{n}_pct"] = _pct_diff(c.iloc[-1], ema.iloc[-1])

    ema9 = ta.trend.ema_indicator(c, window=9)
    ema21 = ta.trend.ema_indicator(c, window=21)
    f["ema_9_21_diff_pct"] = _pct_diff(ema9.iloc[-1], ema21.iloc[-1])
    f["ema_9_21_bull_cross"] = int(ema9.iloc[-2] < ema21.iloc[-2] and ema9.iloc[-1] >= ema21.iloc[-1])
    f["ema_9_21_bear_cross"] = int(ema9.iloc[-2] > ema21.iloc[-2] and ema9.iloc[-1] <= ema21.iloc[-1])

    macd = ta.trend.MACD(c)
    macd_line, macd_sig = macd.macd(), macd.macd_signal()
    f["macd"] = macd_line.iloc[-1]
    f["macd_signal"] = macd_sig.iloc[-1]
    f["macd_diff"] = macd.macd_diff().iloc[-1]
    f["macd_bull_cross"] = int(macd_line.iloc[-2] < macd_sig.iloc[-2] and macd_line.iloc[-1] >= macd_sig.iloc[-1])
    f["macd_slope"] = macd_line.diff().iloc[-1]

    adx_ind = ta.trend.ADXIndicator(df["high"], df["low"], c)
    f["adx_14"] = adx_ind.adx().iloc[-1]
    f["plus_di"] = adx_ind.adx_pos().iloc[-1]
    f["minus_di"] = adx_ind.adx_neg().iloc[-1]
    f["di_diff"] = f["plus_di"] - f["minus_di"] if f["plus_di"] is not None and f["minus_di"] is not None else np.nan
    f["trend_strength_bucket"] = 1 if (f["adx_14"] or 0) > 25 else 0

    aroon = ta.trend.AroonIndicator(df["high"], df["low"])
    f["aroon_up"] = aroon.aroon_up().iloc[-1]
    f["aroon_down"] = aroon.aroon_down().iloc[-1]
    f["aroon_oscillator"] = f["aroon_up"] - f["aroon_down"] if f["aroon_up"] is not None else np.nan

    ichimoku = ta.trend.IchimokuIndicator(df["high"], df["low"])
    f["ichimoku_a"] = ichimoku.ichimoku_a().iloc[-1]
    f["ichimoku_b"] = ichimoku.ichimoku_b().iloc[-1]
    f["price_above_cloud"] = int(c.iloc[-1] > max(f["ichimoku_a"] or 0, f["ichimoku_b"] or 0))

    psar = ta.trend.PSARIndicator(df["high"], df["low"], c)
    f["psar"] = psar.psar().iloc[-1]
    f["price_above_psar"] = int(c.iloc[-1] > (f["psar"] or c.iloc[-1]))

    return f


# ---------------------------------------------------------------------------
# 3. Momentum
# ---------------------------------------------------------------------------

def _momentum_features(df: pd.DataFrame) -> dict:
    c, h, l = df["close"], df["high"], df["low"]
    f = {}
    for n in (7, 14, 21):
        f[f"rsi_{n}"] = ta.momentum.rsi(c, window=n).iloc[-1]
    stoch = ta.momentum.StochasticOscillator(h, l, c)
    f["stoch_k"] = stoch.stoch().iloc[-1]
    f["stoch_d"] = stoch.stoch_signal().iloc[-1]
    f["stoch_overbought"] = int((f["stoch_k"] or 0) > 80)
    f["stoch_oversold"] = int((f["stoch_k"] or 0) < 20)
    f["williams_r"] = ta.momentum.williams_r(h, l, c).iloc[-1]
    for n in (5, 10, 20):
        f[f"roc_{n}"] = ta.momentum.roc(c, window=n).iloc[-1]
    f["cci_14"] = ta.trend.cci(h, l, c, window=14).iloc[-1]
    f["tsi"] = ta.momentum.tsi(c).iloc[-1]
    f["ultimate_oscillator"] = ta.momentum.ultimate_oscillator(h, l, c).iloc[-1]
    f["awesome_oscillator"] = ta.momentum.awesome_oscillator(h, l).iloc[-1]
    f["kama"] = ta.momentum.kama(c).iloc[-1]
    return f


# ---------------------------------------------------------------------------
# 4. Volatilitaet
# ---------------------------------------------------------------------------

def _volatility_features(df: pd.DataFrame) -> dict:
    c, h, l = df["close"], df["high"], df["low"]
    f = {}
    atr = ta.volatility.average_true_range(h, l, c)
    f["atr_14"] = atr.iloc[-1]
    f["atr_pct_of_price"] = _pct_diff(atr.iloc[-1] + c.iloc[-1], c.iloc[-1])
    bb = ta.volatility.BollingerBands(c)
    f["bb_width_pct"] = ((bb.bollinger_hband() - bb.bollinger_lband()) / bb.bollinger_mavg()).iloc[-1]
    f["bb_percent_b"] = bb.bollinger_pband().iloc[-1]
    kelt = ta.volatility.KeltnerChannel(h, l, c)
    f["keltner_width_pct"] = ((kelt.keltner_channel_hband() - kelt.keltner_channel_lband())
                               / kelt.keltner_channel_mband()).iloc[-1]
    dc = ta.volatility.DonchianChannel(h, l, c)
    f["donchian_width_pct"] = ((dc.donchian_channel_hband() - dc.donchian_channel_lband())
                                / c).iloc[-1]
    returns = c.pct_change()
    for n in (10, 20):
        f[f"realized_vol_{n}"] = returns.rolling(n).std().iloc[-1]
    f["ulcer_index"] = ta.volatility.ulcer_index(c).iloc[-1]
    f["true_range_last"] = max(h.iloc[-1] - l.iloc[-1], abs(h.iloc[-1] - c.iloc[-2]), abs(l.iloc[-1] - c.iloc[-2]))
    f["volatility_regime"] = 1 if (f["realized_vol_20"] or 0) > (returns.rolling(100).std().iloc[-1] or 0) else 0
    return f


# ---------------------------------------------------------------------------
# 5. Volumen
# ---------------------------------------------------------------------------

def _volume_features(df: pd.DataFrame) -> dict:
    f = {}
    if "volume" not in df.columns:
        return f
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]
    obv = ta.volume.on_balance_volume(c, v)
    f["obv"] = obv.iloc[-1]
    f["obv_slope_5"] = obv.diff(5).iloc[-1]
    f["volume_sma_20"] = v.rolling(20).mean().iloc[-1]
    f["volume_zscore_20"] = ((v.iloc[-1] - v.rolling(20).mean().iloc[-1]) / v.rolling(20).std().iloc[-1]
                              if v.rolling(20).std().iloc[-1] not in (0, None) else np.nan)
    f["volume_spike"] = int((f["volume_zscore_20"] or 0) > 2)
    vwap = ta.volume.volume_weighted_average_price(h, l, c, v)
    f["vwap"] = vwap.iloc[-1]
    f["price_vs_vwap_pct"] = _pct_diff(c.iloc[-1], vwap.iloc[-1])
    f["mfi_14"] = ta.volume.money_flow_index(h, l, c, v).iloc[-1]
    f["cmf_20"] = ta.volume.chaikin_money_flow(h, l, c, v).iloc[-1]
    f["force_index_13"] = ta.volume.force_index(c, v, window=13).iloc[-1]
    return f


# ---------------------------------------------------------------------------
# 6. Breakout-Erkennung
# ---------------------------------------------------------------------------

def _breakout_features(df: pd.DataFrame) -> dict:
    c, h, l = df["close"], df["high"], df["low"]
    f = {}
    for n in (20, 50, 100):
        hh = h.rolling(n).max()
        ll = l.rolling(n).min()
        f[f"donchian_high_{n}"] = hh.iloc[-1]
        f[f"donchian_low_{n}"] = ll.iloc[-1]
        f[f"breakout_up_{n}"] = int(c.iloc[-1] >= hh.shift(1).iloc[-1])
        f[f"breakout_down_{n}"] = int(c.iloc[-1] <= ll.shift(1).iloc[-1])
        f[f"distance_to_high_{n}_pct"] = _pct_diff(hh.iloc[-1], c.iloc[-1])
        f[f"distance_to_low_{n}_pct"] = _pct_diff(c.iloc[-1], ll.iloc[-1])

    # Baelken seit letztem Ausbruch (20er Fenster)
    hh20 = h.rolling(20).max().shift(1)
    breakout_series = (c >= hh20).astype(int)
    idx_last_breakout = breakout_series[breakout_series == 1].index
    f["bars_since_breakout_up_20"] = (
        len(c) - 1 - c.index.get_loc(idx_last_breakout[-1]) if len(idx_last_breakout) else np.nan
    )

    avg_range = (h - l).rolling(20).mean()
    f["range_expansion_ratio"] = ((h.iloc[-1] - l.iloc[-1]) / avg_range.iloc[-1]
                                   if avg_range.iloc[-1] else np.nan)
    atr = ta.volatility.average_true_range(h, l, c)
    f["volatility_breakout"] = int(abs(c.iloc[-1] - c.iloc[-2]) > 1.5 * (atr.iloc[-1] or 0))
    f["new_high_100"] = int(c.iloc[-1] >= c.rolling(100).max().iloc[-1])
    f["new_low_100"] = int(c.iloc[-1] <= c.rolling(100).min().iloc[-1])
    return f


# ---------------------------------------------------------------------------
# 7. Support/Resistance & Pivots
# ---------------------------------------------------------------------------

def _pivot_features(df: pd.DataFrame) -> dict:
    prev = df.iloc[-2]
    pivot = (prev["high"] + prev["low"] + prev["close"]) / 3
    r1 = 2 * pivot - prev["low"]
    s1 = 2 * pivot - prev["high"]
    r2 = pivot + (prev["high"] - prev["low"])
    s2 = pivot - (prev["high"] - prev["low"])
    c = df["close"].iloc[-1]
    return {
        "pivot_point": pivot, "resistance_1": r1, "support_1": s1,
        "resistance_2": r2, "support_2": s2,
        "distance_to_pivot_pct": _pct_diff(c, pivot),
        "distance_to_r1_pct": _pct_diff(r1, c),
        "distance_to_s1_pct": _pct_diff(c, s1),
        "price_above_pivot": int(c > pivot),
    }


# ---------------------------------------------------------------------------
# 8. Fibonacci
# ---------------------------------------------------------------------------

def _fibonacci_features(df: pd.DataFrame, lookback: int = 100) -> dict:
    window = df.tail(lookback)
    hi, lo = window["high"].max(), window["low"].min()
    diff = hi - lo
    c = df["close"].iloc[-1]
    levels = {"fib_0": hi, "fib_236": hi - 0.236 * diff, "fib_382": hi - 0.382 * diff,
              "fib_5": hi - 0.5 * diff, "fib_618": hi - 0.618 * diff,
              "fib_786": hi - 0.786 * diff, "fib_100": lo}
    f = dict(levels)
    f["distance_to_fib_618_pct"] = _pct_diff(c, levels["fib_618"])
    f["distance_to_fib_5_pct"] = _pct_diff(c, levels["fib_5"])
    f["in_golden_zone"] = int(levels["fib_618"] <= c <= levels["fib_5"] or levels["fib_5"] <= c <= levels["fib_618"])
    return f


# ---------------------------------------------------------------------------
# 9. Candlestick-Patterns (einfache, robuste Regeln)
# ---------------------------------------------------------------------------

def _candlestick_features(df: pd.DataFrame) -> dict:
    o, h, l, c = df["open"].iloc[-1], df["high"].iloc[-1], df["low"].iloc[-1], df["close"].iloc[-1]
    po, pc = df["open"].iloc[-2], df["close"].iloc[-2]
    body = abs(c - o)
    full_range = max(h - l, 1e-9)
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    f = {
        "body_pct_of_range": body / full_range,
        "upper_wick_pct_of_range": upper_wick / full_range,
        "lower_wick_pct_of_range": lower_wick / full_range,
        "is_bullish_candle": int(c > o),
        "is_doji": int(body / full_range < 0.1),
        "is_hammer": int(lower_wick > 2 * body and upper_wick < body),
        "is_shooting_star": int(upper_wick > 2 * body and lower_wick < body),
        "is_marubozu": int(body / full_range > 0.9),
        "is_bullish_engulfing": int(c > o and pc < po and c > po and o < pc),
        "is_bearish_engulfing": int(c < o and pc > po and c < po and o > pc),
        "gap_up": int(df["open"].iloc[-1] > df["high"].iloc[-2]),
        "gap_down": int(df["open"].iloc[-1] < df["low"].iloc[-2]),
    }
    return f


# ---------------------------------------------------------------------------
# 10. Stop-Loss / Risikomanagement
# ---------------------------------------------------------------------------

def _risk_features(df: pd.DataFrame, atr_mult: float = 1.5, swing_lookback: int = 20) -> dict:
    c = df["close"].iloc[-1]
    atr = ta.volatility.average_true_range(df["high"], df["low"], df["close"]).iloc[-1] or 0
    swing_low = df["low"].tail(swing_lookback).min()
    swing_high = df["high"].tail(swing_lookback).max()
    atr_stop_long = c - atr_mult * atr
    atr_stop_short = c + atr_mult * atr
    f = {
        "atr_stop_long": atr_stop_long,
        "atr_stop_short": atr_stop_short,
        "distance_to_atr_stop_long_pct": _pct_diff(c, atr_stop_long),
        "distance_to_atr_stop_short_pct": _pct_diff(atr_stop_short, c),
        "swing_low_stop": swing_low,
        "swing_high_stop": swing_high,
        "distance_to_swing_low_stop_pct": _pct_diff(c, swing_low),
        "distance_to_swing_high_stop_pct": _pct_diff(swing_high, c),
        "risk_per_unit_atr": atr,
        "suggested_risk_reward_2r_long": c + 2 * (c - atr_stop_long),
        "suggested_risk_reward_2r_short": c - 2 * (atr_stop_short - c),
        "volatility_based_position_scale": (1 / atr) if atr else np.nan,
    }
    return f


# ---------------------------------------------------------------------------
# 11. Session / Zeit
# ---------------------------------------------------------------------------

def _session_features(df: pd.DataFrame) -> dict:
    ts = df.index[-1]
    hour = ts.hour
    f = {
        "hour_of_day": hour,
        "day_of_week": ts.dayofweek,
        "day_of_month": ts.day,
        "is_month_start": int(ts.is_month_start),
        "is_month_end": int(ts.is_month_end),
        "is_asian_session": int(0 <= hour < 8),
        "is_london_session": int(7 <= hour < 16),
        "is_ny_session": int(12 <= hour < 21),
        "is_london_ny_overlap": int(12 <= hour < 16),
        "is_weekend_adjacent": int(ts.dayofweek in (4, 0)),  # Freitag/Montag
    }
    return f


# ---------------------------------------------------------------------------
# 12. Statistik
# ---------------------------------------------------------------------------

def _statistical_features(df: pd.DataFrame) -> dict:
    c = df["close"]
    returns = c.pct_change().dropna()
    r20 = returns.tail(20)
    f = {
        "skewness_20": r20.skew(),
        "kurtosis_20": r20.kurt(),
        "autocorr_lag1_20": r20.autocorr(lag=1),
        "zscore_price_20": ((c.iloc[-1] - c.tail(20).mean()) / c.tail(20).std()
                             if c.tail(20).std() else np.nan),
        "percentile_rank_price_50": (c.tail(50).rank(pct=True).iloc[-1]),
        "coefficient_of_variation_20": (c.tail(20).std() / c.tail(20).mean()
                                         if c.tail(20).mean() else np.nan),
    }
    return f


# ---------------------------------------------------------------------------
# 14. Regime/Trend (aus dem eigenstaendigen regime.py-Modul)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Erweiterte Indikatoren (aus dem eigenstaendigen extended_indicators.py-Modul)
# ---------------------------------------------------------------------------

def _extended_indicator_features(df: pd.DataFrame) -> dict:
    try:
        return ext_mod.compute_extended_indicators(df)
    except AssertionError:
        return {}


def _regime_features(df: pd.DataFrame) -> dict:
    try:
        r = regime_mod.detect_regime(df)
    except AssertionError:
        return {}
    f = {f"regime_{k}": v for k, v in r.items()}
    # Zusaetzlich als numerische One-Hot-Flags, damit ein RL-Modell die
    # kategorischen Labels nicht erst selbst encodieren muss.
    f["regime_direction_up"] = int(r["trend_direction"] == "up")
    f["regime_direction_down"] = int(r["trend_direction"] == "down")
    f["regime_direction_sideways"] = int(r["trend_direction"] == "sideways")
    f["regime_strength_strong"] = int(r["trend_strength"] == "strong")
    f["regime_strength_weak"] = int(r["trend_strength"] == "weak")
    f["regime_structure_bullish"] = int(r["market_structure"] == "higher_highs_higher_lows")
    f["regime_structure_bearish"] = int(r["market_structure"] == "lower_highs_lower_lows")
    f["regime_volatility_high"] = int(r["volatility_regime"] == "high")
    f["regime_volatility_low"] = int(r["volatility_regime"] == "low")
    return f


# ---------------------------------------------------------------------------
# Positions-State (optional, wird vom RL-Environment mitgegeben)
# ---------------------------------------------------------------------------

def _position_state_features(position_state: dict | None) -> dict:
    """
    position_state (optional dict vom Environment), z.B.:
    {
        "side": "long" | "short" | "flat",
        "entry_price": 2350.5,
        "current_price": 2360.0,
        "bars_held": 12,
        "stop_loss": 2340.0,
        "take_profit": 2380.0,
        "peak_equity": 10500.0,
        "current_equity": 10200.0,
        "consecutive_wins": 2,
        "consecutive_losses": 0,
    }
    Ohne uebergebenen State werden neutrale Defaults (flat) zurueckgegeben,
    damit der Feature-Vektor immer dieselbe Laenge/Form hat (wichtig fuer RL).
    """
    ps = position_state or {}
    side = ps.get("side", "flat")
    entry = ps.get("entry_price")
    price = ps.get("current_price")
    unrealized_pnl_pct = _pct_diff(price, entry) if (entry and price and side == "long") else (
        _pct_diff(entry, price) if (entry and price and side == "short") else 0.0
    )
    stop = ps.get("stop_loss")
    tp = ps.get("take_profit")
    peak_eq = ps.get("peak_equity")
    cur_eq = ps.get("current_equity")
    return {
        "position_side_long": int(side == "long"),
        "position_side_short": int(side == "short"),
        "position_side_flat": int(side == "flat"),
        "bars_held": ps.get("bars_held", 0),
        "unrealized_pnl_pct": unrealized_pnl_pct or 0.0,
        "distance_to_stop_loss_pct": (_pct_diff(price, stop) if price and stop else np.nan),
        "distance_to_take_profit_pct": (_pct_diff(tp, price) if price and tp else np.nan),
        "equity_drawdown_pct": (_pct_diff(cur_eq, peak_eq) if cur_eq and peak_eq else 0.0),
        "consecutive_wins": ps.get("consecutive_wins", 0),
        "consecutive_losses": ps.get("consecutive_losses", 0),
    }


# ---------------------------------------------------------------------------
# Zusammenfuehrung
# ---------------------------------------------------------------------------

def build_feature_vector(df: pd.DataFrame, position_state: dict | None = None) -> dict:
    """
    Baut den vollstaendigen RL-Feature-Vektor (100+ Keys) fuer den letzten
    Zeitpunkt in `df`. `position_state` ist optional und wird vom
    RL-Environment/Trading-Loop uebergeben, falls gerade eine Position offen ist.
    """
    assert len(df) >= 210, "Mindestens 210 Kerzen Historie empfohlen (wegen sma_200 etc.)"

    raw = {}
    raw.update(_price_features(df))
    raw.update(_trend_features(df))
    raw.update(_momentum_features(df))
    raw.update(_volatility_features(df))
    raw.update(_volume_features(df))
    raw.update(_breakout_features(df))
    raw.update(_pivot_features(df))
    raw.update(_fibonacci_features(df))
    raw.update(_candlestick_features(df))
    raw.update(_risk_features(df))
    raw.update(_session_features(df))
    raw.update(_statistical_features(df))
    raw.update(_extended_indicator_features(df))
    raw.update(_regime_features(df))
    raw.update(_position_state_features(position_state))

    return {k: _safe(v) for k, v in raw.items()}


# ---------------------------------------------------------------------------
# Modell-taugliches Feature-Set (skaleninvariant)
# ---------------------------------------------------------------------------
# Absolute Preis-/Volumenniveaus (z.B. sma_20, pivot_point, vwap) tragen die
# Groessenordnung des jeweiligen Instruments (Gold ~2300, ein Altcoin ~0.002).
# Ein RL-Modell, das auf solchen Rohwerten trainiert, generalisiert nicht
# zwischen Instrumenten/Zeitraeumen. Diese Keys sind deshalb im 'model'-Set
# bewusst ausgeschlossen -- die dazugehoerigen *_pct-/Distanz-Varianten
# bleiben erhalten und tragen dieselbe Information skaleninvariant.
ABSOLUTE_PRICE_KEYS = {
    # Trend/MA (Rohwerte -- price_vs_*_pct-Varianten bleiben im Modell-Set)
    "sma_10", "sma_20", "sma_50", "sma_100", "sma_200",
    "ema_9", "ema_21", "ema_50", "ema_200",
    "macd", "macd_signal", "macd_diff", "macd_slope",
    "ichimoku_a", "ichimoku_b", "psar",
    # Momentum (preisskalierte Rohwerte)
    "kama", "awesome_oscillator",
    # Volatilitaet (Rohwerte -- *_pct-Varianten bleiben)
    "atr_14", "true_range_last",
    # Volumen (instrumentabhaengige Rohgroessen)
    "obv", "obv_slope_5", "volume_sma_20", "vwap", "force_index_13",
    # Breakout (Rohpreise -- distance_to_*_pct bleibt)
    "donchian_high_20", "donchian_low_20", "donchian_high_50", "donchian_low_50",
    "donchian_high_100", "donchian_low_100",
    # Pivots (Rohpreise -- distance_to_*_pct bleibt)
    "pivot_point", "resistance_1", "support_1", "resistance_2", "support_2",
    # Fibonacci (Rohpreise -- distance_to_fib_*_pct bleibt)
    "fib_0", "fib_236", "fib_382", "fib_5", "fib_618", "fib_786", "fib_100",
    # Stop-Loss/Risiko (Rohpreise -- distance_to_*_pct bleibt)
    "atr_stop_long", "atr_stop_short", "swing_low_stop", "swing_high_stop",
    "risk_per_unit_atr", "suggested_risk_reward_2r_long", "suggested_risk_reward_2r_short",
    "volatility_based_position_scale",
    # Erweiterte Indikatoren (Rohpreise/kumulative Volumengroessen -- *_pct-Varianten bleiben)
    "dpo", "adl", "nvi", "pvt", "hull_ma_9", "vwma_20", "supertrend_value",
    "alligator_jaw", "alligator_teeth", "alligator_lips",
}


def build_model_feature_vector(df: pd.DataFrame, position_state: dict | None = None) -> dict:
    """
    Wie build_feature_vector(), aber gefiltert auf ein skaleninvariantes
    Feature-Set: entfernt absolute Preis-/Volumenniveaus (ABSOLUTE_PRICE_KEYS)
    sowie kategorische String-Werte (z.B. regime_regime_label -- die Information
    steckt bereits in den One-Hot-Flags regime_direction_up etc.).

    Das ist das Set, das tatsaechlich in den RL-Observation-Space gehoert.
    build_feature_vector() bleibt fuer Menschen/Debugging/Dashboards nuetzlich,
    wo absolute Preise Sinn ergeben.
    """
    full = build_feature_vector(df, position_state)
    return {
        k: v for k, v in full.items()
        if k not in ABSOLUTE_PRICE_KEYS and not isinstance(v, str)
    }


# ---------------------------------------------------------------------------
# Feature-Schema-Versionierung
# ---------------------------------------------------------------------------
# Bei jeder inhaltlichen Aenderung an den obigen _*_features()-Funktionen
# (neues Feature, entferntes Feature, umbenannter Key) MUSS diese Version
# erhoeht werden. Ein bereits trainiertes RL-Modell erwartet einen Vektor
# fester Laenge/Reihenfolge -- ohne Versionsnummer merkt man eine
# Schema-Aenderung erst an kryptischen Trainingsfehlern oder, schlimmer,
# gar nicht (stilles Fehltraining mit vertauschten Feature-Spalten).
FEATURE_SCHEMA_VERSION = "1.1.0"


def feature_schema_hash(feature_dict: dict) -> str:
    """Kurzer Hash ueber die sortierten Feature-Keys (nicht die Werte!).
    Zwei Aufrufe mit demselben Hash garantieren: gleiche Keys, gleiche Reihenfolge
    nach Sortierung -- ein RL-Modell kann sich also auf dieselbe Vektorform verlassen.
    Aendert sich der Hash, hat sich das Schema geaendert -> Modell ggf. neu trainieren.
    """
    key_string = ",".join(sorted(feature_dict.keys()))
    return hashlib.sha256(key_string.encode()).hexdigest()[:12]
