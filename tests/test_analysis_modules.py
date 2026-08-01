"""Tests fuer die quellenunabhaengigen Analyse-Module. Brauchen kein
Netzwerk -- reine Berechnung auf synthetischen OHLCV-Daten."""
import pandas as pd


def test_build_feature_vector_counts(synthetic_ohlcv):
    from market_analysis_by_chrisx47b.rl_features import (
        build_feature_vector, build_model_feature_vector, ABSOLUTE_PRICE_KEYS,
    )
    df = synthetic_ohlcv(n=400)
    raw = build_feature_vector(df)
    model = build_model_feature_vector(df)

    assert len(raw) == 249
    assert len(model) == 183
    # Keine absoluten Preisniveaus duerfen ins Modell-Set durchrutschen
    leaked = ABSOLUTE_PRICE_KEYS & set(model.keys())
    assert not leaked, f"Absolute Preis-Keys im Modell-Set: {leaked}"
    # Keine Strings im Modell-Set (z.B. regime_regime_label)
    assert all(not isinstance(v, str) for v in model.values())


def test_core_feature_set_all_keys_exist_in_model_vector(synthetic_ohlcv):
    from market_analysis_by_chrisx47b.rl_features import build_model_feature_vector
    from market_analysis_by_chrisx47b.feature_selection import CORE_FEATURE_SET, build_core_feature_vector
    df = synthetic_ohlcv(n=400)
    model = build_model_feature_vector(df)
    core = build_core_feature_vector(model)
    missing = set(CORE_FEATURE_SET) - set(model.keys())
    assert not missing, f"CORE_FEATURE_SET verweist auf nicht existierende Keys: {missing}"
    assert len(core) == len(CORE_FEATURE_SET)


def test_feature_schema_hash_is_stable(synthetic_ohlcv):
    from market_analysis_by_chrisx47b.rl_features import build_model_feature_vector, feature_schema_hash
    df = synthetic_ohlcv(n=400)
    v1 = feature_schema_hash(build_model_feature_vector(df))
    v2 = feature_schema_hash(build_model_feature_vector(synthetic_ohlcv(n=400, seed=99)))
    assert v1 == v2  # gleiches Schema (Keys), unabhaengig von den Werten


def test_regime_detects_strong_uptrend(synthetic_ohlcv):
    from market_analysis_by_chrisx47b.regime import detect_regime
    df = synthetic_ohlcv(n=300, drift=0.6, noise=0.15)
    r = detect_regime(df)
    assert r["trend_direction"] == "up"
    assert r["trend_strength"] == "strong"
    # Marktstruktur (HH/HL) haengt zusaetzlich von der Rausch-Verteilung der
    # Swing-Punkte ab -- kann bei synthetischen Daten trotz starkem Trend
    # 'mixed' sein (kein Bug, siehe regime.py-Docstring zur Hurst-Naeherung).


def test_regime_detects_strong_downtrend(synthetic_ohlcv):
    from market_analysis_by_chrisx47b.regime import detect_regime
    df = synthetic_ohlcv(n=300, drift=-0.6, noise=0.15)
    r = detect_regime(df)
    assert r["trend_direction"] == "down"
    assert r["trend_strength"] == "strong"


def test_chart_patterns_detects_constructed_double_top():
    import numpy as np
    n = 120
    price = np.concatenate([
        np.linspace(100, 130, 30), np.linspace(130, 110, 20),
        np.linspace(110, 130, 20), np.linspace(130, 100, 50),
    ])
    idx = pd.date_range("2024-01-01", periods=n, freq="h")
    df = pd.DataFrame({"open": price, "high": price + 0.5, "low": price - 0.5,
                        "close": price, "volume": [500] * n}, index=idx)
    from market_analysis_by_chrisx47b.chart_patterns import detect_chart_patterns
    patterns = detect_chart_patterns(df, swing_window=4, min_confidence=0.1)
    names = [p["pattern"] for p in patterns]
    assert "double_top" in names


def test_stop_management_ratchet_never_loosens():
    from market_analysis_by_chrisx47b.stop_management import update_trailing_stop
    s1 = update_trailing_stop(100, 105, "long")
    assert s1 == 105
    s2 = update_trailing_stop(s1, 98, "long")  # Versuch zu senken
    assert s2 == 105  # darf nicht sinken

    s1_short = update_trailing_stop(100, 95, "short")
    assert s1_short == 95
    s2_short = update_trailing_stop(s1_short, 110, "short")  # Versuch zu erhoehen
    assert s2_short == 95  # darf nicht steigen


def test_stop_management_breakeven_triggers_at_r_multiple():
    from market_analysis_by_chrisx47b.stop_management import move_to_breakeven
    result = move_to_breakeven(entry_price=100, current_price=103, side="long",
                                current_stop=97, trigger_r_multiple=1.0, initial_risk=3)
    assert result["triggered"] is True
    assert result["stop_price"] >= 100  # mindestens Breakeven


def test_extended_indicators_supertrend_direction(synthetic_ohlcv):
    from market_analysis_by_chrisx47b.extended_indicators import compute_extended_indicators
    df = synthetic_ohlcv(n=200, drift=0.3, noise=0.2)  # klarer Aufwaertstrend
    result = compute_extended_indicators(df)
    assert result["supertrend_direction"] in (1, -1)
    assert 0 <= result["connors_rsi"] <= 100


def test_data_quality_detects_inconsistent_ohlc():
    from market_analysis_by_chrisx47b.data_quality import validate_ohlcv
    df = pd.DataFrame({"open": [1, 2], "high": [0.5, 1], "low": [2, 3], "close": [1, 2]})
    result = validate_ohlcv(df)
    assert result["is_valid"] is False
    assert any("inkonsistent" in issue for issue in result["issues"])


def test_data_quality_valid_data_passes(synthetic_ohlcv):
    from market_analysis_by_chrisx47b.data_quality import validate_ohlcv
    df = synthetic_ohlcv(n=300)
    result = validate_ohlcv(df)
    assert result["is_valid"] is True
