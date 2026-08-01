"""
Chart-Pattern-Erkennung -- regelbasiert auf Swing-Punkten, KEIN ML-Modell.

Ehrlicher Hinweis: klassische Chartmuster sind per Definition subjektiv/
fuzzy (auch erfahrene Trader sind sich oft uneinig, ob ein Muster "echt" ist).
Diese Implementierung nutzt geometrische Naeherungen (Toleranzbaender,
Trendlinien-Steigungen ueber lineare Regression) und liefert einen
Konfidenz-Score -- keine binaere Wahrheit. Als zusaetzliches Signal gedacht,
nicht als alleinige Handelsgrundlage.
"""

from __future__ import annotations
import numpy as np
import pandas as pd


def find_swing_points(df: pd.DataFrame, window: int = 5) -> dict:
    """Findet lokale Swing-Highs/-Lows: ein Punkt ist ein Swing-High, wenn er
    das Maximum in einem Fenster von `window` Kerzen davor/danach ist (analog
    fuer Swing-Lows). Gibt zwei Listen von (index_position, timestamp, price) zurueck.
    """
    highs, lows = df["high"], df["low"]
    swing_highs, swing_lows = [], []
    for i in range(window, len(df) - window):
        seg_h = highs.iloc[i - window: i + window + 1]
        seg_l = lows.iloc[i - window: i + window + 1]
        if highs.iloc[i] == seg_h.max():
            swing_highs.append((i, df.index[i], float(highs.iloc[i])))
        if lows.iloc[i] == seg_l.min():
            swing_lows.append((i, df.index[i], float(lows.iloc[i])))
    return {"highs": swing_highs, "lows": swing_lows}


def _slope_r2(points: list[tuple]) -> dict:
    """Lineare Regression ueber (index_position, price)-Paare -> Steigung
    (normalisiert auf % pro Kerze relativ zum mittleren Preis) + R^2."""
    if len(points) < 2:
        return {"slope_pct": 0.0, "r_squared": 0.0}
    x = np.array([p[0] for p in points], dtype=float)
    y = np.array([p[2] for p in points], dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    y_pred = slope * x + intercept
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return {"slope_pct": float(slope / y.mean()) if y.mean() else 0.0, "r_squared": float(r2)}


def _pct_diff(a: float, b: float) -> float:
    return abs(a - b) / b if b else 0.0


def detect_double_top(swings: dict, tolerance_pct: float = 0.02) -> dict | None:
    highs = swings["highs"]
    if len(highs) < 2:
        return None
    h1, h2 = highs[-2], highs[-1]
    diff = _pct_diff(h1[2], h2[2])
    if diff <= tolerance_pct:
        confidence = round(max(0.0, 1 - diff / tolerance_pct), 3)
        return {"pattern": "double_top", "confidence": confidence,
                "peak_1": {"timestamp": str(h1[1]), "price": h1[2]},
                "peak_2": {"timestamp": str(h2[1]), "price": h2[2]}}
    return None


def detect_double_bottom(swings: dict, tolerance_pct: float = 0.02) -> dict | None:
    lows = swings["lows"]
    if len(lows) < 2:
        return None
    l1, l2 = lows[-2], lows[-1]
    diff = _pct_diff(l1[2], l2[2])
    if diff <= tolerance_pct:
        confidence = round(max(0.0, 1 - diff / tolerance_pct), 3)
        return {"pattern": "double_bottom", "confidence": confidence,
                "trough_1": {"timestamp": str(l1[1]), "price": l1[2]},
                "trough_2": {"timestamp": str(l2[1]), "price": l2[2]}}
    return None


def detect_head_and_shoulders(swings: dict, shoulder_tolerance_pct: float = 0.03) -> dict | None:
    highs = swings["highs"]
    if len(highs) < 3:
        return None
    left, head, right = highs[-3], highs[-2], highs[-1]
    if head[2] > left[2] and head[2] > right[2]:
        shoulder_diff = _pct_diff(left[2], right[2])
        if shoulder_diff <= shoulder_tolerance_pct:
            confidence = round(max(0.0, 1 - shoulder_diff / shoulder_tolerance_pct), 3)
            return {"pattern": "head_and_shoulders", "confidence": confidence,
                    "left_shoulder": {"timestamp": str(left[1]), "price": left[2]},
                    "head": {"timestamp": str(head[1]), "price": head[2]},
                    "right_shoulder": {"timestamp": str(right[1]), "price": right[2]}}
    return None


def detect_inverse_head_and_shoulders(swings: dict, shoulder_tolerance_pct: float = 0.03) -> dict | None:
    lows = swings["lows"]
    if len(lows) < 3:
        return None
    left, head, right = lows[-3], lows[-2], lows[-1]
    if head[2] < left[2] and head[2] < right[2]:
        shoulder_diff = _pct_diff(left[2], right[2])
        if shoulder_diff <= shoulder_tolerance_pct:
            confidence = round(max(0.0, 1 - shoulder_diff / shoulder_tolerance_pct), 3)
            return {"pattern": "inverse_head_and_shoulders", "confidence": confidence,
                    "left_shoulder": {"timestamp": str(left[1]), "price": left[2]},
                    "head": {"timestamp": str(head[1]), "price": head[2]},
                    "right_shoulder": {"timestamp": str(right[1]), "price": right[2]}}
    return None


def detect_triangle_or_wedge(swings: dict, n_points: int = 4, flat_threshold: float = 0.0015) -> dict | None:
    """Klassifiziert ueber die Steigungen der letzten `n_points` Swing-Highs
    (obere Trendlinie) und Swing-Lows (untere Trendlinie):
      - Ascending Triangle: obere ~flach, untere steigend
      - Descending Triangle: obere fallend, untere ~flach
      - Symmetrical Triangle: obere fallend, untere steigend (konvergierend)
      - Rising Wedge: beide steigend, obere flacher als untere (konvergierend)
      - Falling Wedge: beide fallend, untere flacher als obere (konvergierend)
    """
    highs, lows = swings["highs"][-n_points:], swings["lows"][-n_points:]
    if len(highs) < 3 or len(lows) < 3:
        return None

    upper = _slope_r2(highs)
    lower = _slope_r2(lows)
    up_slope, low_slope = upper["slope_pct"], lower["slope_pct"]
    avg_r2 = round((upper["r_squared"] + lower["r_squared"]) / 2, 3)

    upper_flat = abs(up_slope) < flat_threshold
    lower_flat = abs(low_slope) < flat_threshold

    pattern = None
    if upper_flat and low_slope > flat_threshold:
        pattern = "ascending_triangle"
    elif lower_flat and up_slope < -flat_threshold:
        pattern = "descending_triangle"
    elif up_slope < -flat_threshold and low_slope > flat_threshold:
        pattern = "symmetrical_triangle"
    elif up_slope > flat_threshold and low_slope > flat_threshold and low_slope > up_slope:
        pattern = "rising_wedge"
    elif up_slope < -flat_threshold and low_slope < -flat_threshold and up_slope < low_slope:
        pattern = "falling_wedge"

    if pattern is None:
        return None
    return {"pattern": pattern, "confidence": avg_r2,
            "upper_trendline_slope_pct": round(up_slope, 5),
            "lower_trendline_slope_pct": round(low_slope, 5)}


def detect_chart_patterns(df: pd.DataFrame, swing_window: int = 5, min_confidence: float = 0.3) -> list[dict]:
    """Fuehrt alle Detektoren aus und gibt nur Treffer mit
    confidence >= min_confidence zurueck, sortiert nach Konfidenz absteigend.
    """
    assert len(df) >= swing_window * 4, "Zu wenig Kerzen fuer eine sinnvolle Swing-Erkennung"
    swings = find_swing_points(df, window=swing_window)

    detectors = [
        detect_double_top, detect_double_bottom,
        detect_head_and_shoulders, detect_inverse_head_and_shoulders,
        detect_triangle_or_wedge,
    ]
    results = []
    for fn in detectors:
        r = fn(swings)
        if r and r["confidence"] >= min_confidence:
            results.append(r)
    results.sort(key=lambda r: -r["confidence"])
    return results
