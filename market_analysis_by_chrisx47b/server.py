"""
Market Analysis by chrisx47b
=============================
Marktdaten + Analyse fuer Claude Code aus 5 Quellen: Crypto.com, Binance,
Bybit (alle oeffentlich, kein Key), TradingView (inoffiziell), MetaTrader5
(nur lokal/Windows). Reiner Lese-/Analyse-Connector -- kein Backtesting,
keine Order-Ausfuehrung, keine Anlageberatung.

Kosten-Hinweis: Tool-Docstrings sind bewusst kurz gehalten (jede Zeile hier
wird bei JEDER Nachricht in Claude Code mitgeschickt, nicht nur bei Nutzung).
Ausfuehrliche Begruendungen/Verifikations-Notizen stehen im README, nicht hier.

Start: python server.py
"""

from mcp.server.fastmcp import FastMCP
import pandas as pd

from .sources import crypto_com, tradingview, mt5_source, binance, bybit
from . import source_router
from .rl_features import build_feature_vector, build_model_feature_vector, FEATURE_SCHEMA_VERSION, feature_schema_hash
from .regime import detect_regime
from .extended_indicators import compute_extended_indicators
from . import pinescript_generator as pine_generator
from .data_quality import validate_ohlcv
from .feature_selection import correlation_report, build_core_feature_vector, CORE_FEATURE_SET
from .monitoring import alert_manager, health_monitor, alert_on_data_quality
from .news_filter import get_filtered_news, DEFAULT_FEEDS
from .chart_patterns import detect_chart_patterns
from . import stop_management
from .export import export_ohlcv_csv, export_text_file

mcp = FastMCP("market-analysis-by-chrisx47b")

DISCLAIMER = "Rein informativ/technisch, keine Anlageberatung."


# ---------------------------------------------------------------------------
# Generische Markt-Tools (crypto/binance/bybit/mt5 -- ein Tool statt vier je Aufgabe)
# ---------------------------------------------------------------------------

@mcp.tool()
def candles(symbol: str, source: str = "crypto", timeframe: str = "1h", count: int = 100, category: str = "spot") -> dict:
    """OHLCV-Kerzen. source: crypto/binance/bybit/mt5. category nur fuer bybit (spot/linear/inverse)."""
    df = source_router.get_candles(source, symbol, timeframe, count, category=category)
    return {"symbol": symbol, "source": source, "timeframe": timeframe,
            "candles": df.reset_index().to_dict("records")}


@mcp.tool()
def ticker(symbol: str, source: str = "crypto", category: str = "spot") -> dict:
    """Aktueller Preis/24h-Change/Volumen. source: crypto/binance/bybit (nicht mt5 -> mt5_account_info nutzen)."""
    return source_router.get_ticker(source, symbol, category=category)


@mcp.tool()
def order_book(symbol: str, source: str = "crypto", depth: int = 50, category: str = "spot") -> dict:
    """Orderbuch (Bids/Asks). source: crypto/binance/bybit (nicht mt5)."""
    return source_router.get_order_book(source, symbol, depth, category=category)


# ---------------------------------------------------------------------------
# TradingView
# ---------------------------------------------------------------------------

@mcp.tool()
def tradingview_summary(symbol: str, exchange: str, screener: str, interval: str = "1h") -> dict:
    """TradingView-TA-Rating (inoffiziell). exchange z.B. BINANCE/OANDA. screener: crypto/forex/america/cfd."""
    result = tradingview.get_technical_summary(symbol, exchange, screener, interval)
    result["disclaimer"] = DISCLAIMER
    return result


@mcp.tool()
def create_pinescript_indicator(name: str, components: list[str], overlay: bool = False,
                                 save_to_file: bool = True, output_path: str | None = None) -> dict:
    """Pine-Script-v6-Indikator (sma/ema/rsi/macd/bollinger/atr/supertrend/vwap/adx/stochastic, kombinierbar).
    NICHT compiliert -- im TradingView Pine-Editor pruefen. save_to_file speichert zusaetzlich als .txt lokal.
    """
    code = pine_generator.generate_pine_indicator(name, components, overlay=overlay)
    result = {
        "name": name, "components": components, "pine_script": code,
        "warning": "Nicht compiliert -- im TradingView Pine-Editor verifizieren.",
    }
    if save_to_file:
        result["file"] = export_text_file(code, filepath=output_path, base_name=name.replace(" ", "_"), extension="txt")
    return result


@mcp.tool()
def create_pinescript_strategy(name: str, entry_method: str = "ema_cross", direction: str = "both",
                                exit_method: str = "percent", stop_loss_pct: float = 2.0,
                                take_profit_pct: float = 4.0, atr_stop_mult: float = 2.0,
                                atr_take_profit_mult: float = 4.0, atr_length: int = 14,
                                save_to_file: bool = True, output_path: str | None = None) -> dict:
    """Pine-Script-v6-Strategie (entry_method: ema_cross/rsi_reversion/supertrend_flip/breakout_donchian;
    exit_method: percent/atr). Laeuft in TradingViews eigenem Strategy Tester (dieser Connector backtestet
    selbst nicht). NICHT compiliert -- im Pine-Editor pruefen. save_to_file speichert zusaetzlich als .txt.
    """
    code = pine_generator.generate_pine_strategy(
        name, entry_method=entry_method, direction=direction, exit_method=exit_method,
        stop_loss_pct=stop_loss_pct, take_profit_pct=take_profit_pct,
        atr_stop_mult=atr_stop_mult, atr_take_profit_mult=atr_take_profit_mult, atr_length=atr_length,
    )
    result = {
        "name": name, "entry_method": entry_method, "direction": direction,
        "exit_method": exit_method, "pine_script": code,
        "warning": "Nicht compiliert -- im TradingView Pine-Editor verifizieren/backtesten.",
    }
    if save_to_file:
        result["file"] = export_text_file(code, filepath=output_path, base_name=name.replace(" ", "_"), extension="txt")
    return result


# ---------------------------------------------------------------------------
# MetaTrader5 (nur lokal auf Windows nutzbar -- keine ticker/order_book-Analogie)
# ---------------------------------------------------------------------------

@mcp.tool()
def mt5_account_info() -> dict:
    """Kontostand/Equity/Margin aus MT5."""
    return mt5_source.get_account_info()


@mcp.tool()
def mt5_open_positions() -> list:
    """Aktuell offene Positionen in MT5."""
    return mt5_source.get_open_positions()


@mcp.tool()
def mt5_max_history(symbol: str, timeframe: str = "1h", years_back: float = 6.0, chunk_days: int = 180) -> dict:
    """Holt so viel MT5-Historie wie der Broker vorhaelt (Ziel: years_back Jahre). Nur Metadaten -- volle Kerzen: mt5_download_csv."""
    df = mt5_source.get_max_history(symbol, timeframe, years_back, chunk_days)
    span_years = round((df.index.max() - df.index.min()).days / 365.25, 2)
    return {
        "symbol": symbol, "timeframe": timeframe, "requested_years": years_back,
        "row_count": len(df), "date_range": (str(df.index.min()), str(df.index.max())),
        "actual_years_covered": span_years,
        "note": "Weniger Jahre als angefragt = Broker haelt nicht mehr vor, kein Fehler.",
    }


@mcp.tool()
def mt5_download_csv(symbol: str, timeframe: str = "1h", years_back: float = 6.0,
                      chunk_days: int = 180, output_path: str | None = None) -> dict:
    """Holt maximal verfuegbare MT5-Historie und speichert als CSV lokal (Server laeuft auf deinem Rechner)."""
    df = mt5_source.get_max_history(symbol, timeframe, years_back, chunk_days)
    result = export_ohlcv_csv(df, filepath=output_path, symbol=symbol, timeframe=timeframe)
    result["symbol"] = symbol
    result["timeframe"] = timeframe
    result["requested_years"] = years_back
    return result


# ---------------------------------------------------------------------------
# Regime & erweiterte Indikatoren
# ---------------------------------------------------------------------------

@mcp.tool()
def market_regime(symbol: str, source: str = "crypto", timeframe: str = "1h", count: int = 300) -> dict:
    """Marktregime: Trendrichtung/-staerke, Marktstruktur (HH/HL vs LH/LL), Trending- vs. Mean-Reverting, Volatilitaetsregime."""
    df = source_router.get_candles(source, symbol, timeframe, count)
    regime = detect_regime(df)
    regime["disclaimer"] = DISCLAIMER
    return {"symbol": symbol, "source": source, "timeframe": timeframe, "regime": regime}


@mcp.tool()
def extended_indicators(symbol: str, source: str = "crypto", timeframe: str = "1h",
                         count: int = 200, fields: list[str] | None = None) -> dict:
    """39 Indikatoren (Supertrend/TRIX/KST/DPO/Vortex/PPO/PVO/StochRSI/Hull MA/VWMA/CMO/Chaikin Osc/
    Alligator/Fisher Transform/Connors RSI/ADL/EOM/NVI/PVT/Mass Index). fields: nur diese Keys zurueckgeben
    (spart Tokens bei gezielten Fragen statt aller 39)."""
    df = source_router.get_candles(source, symbol, timeframe, count)
    result = compute_extended_indicators(df)
    if fields:
        result = {k: result[k] for k in fields if k in result}
    return {"symbol": symbol, "source": source, "timeframe": timeframe,
            "indicators": result, "disclaimer": DISCLAIMER}


# ---------------------------------------------------------------------------
# RL-Feature-Vektor
# ---------------------------------------------------------------------------

@mcp.tool()
def rl_feature_vector(symbol: str, source: str = "crypto", timeframe: str = "1h",
                       count: int = 300, position_state: dict | None = None,
                       mode: str = "model", expected_freq: str | None = None,
                       fields: list[str] | None = None) -> dict:
    """RL-State-Vektor (Trend/Momentum/Volatilitaet/Volumen/Breakout/Pivots/Fibonacci/Candlestick/
    Stop-Loss-Distanzen/Session/Statistik/Regime/erweiterte Indikatoren/Positions-State).
    mode='model' (Standard, 183 skaleninvariante Features) oder 'raw' (249, inkl. absoluter Preise).
    fields: nur diese Keys zurueckgeben -- bei gezielten Fragen (z.B. nur RSI) deutlich guenstiger als der volle Vektor.
    source: crypto/binance/bybit/mt5. Fuer einfache Fragen lieber ticker()/market_regime()/extended_indicators() nutzen.
    """
    df = source_router.get_candles(source, symbol, timeframe, count)

    quality = validate_ohlcv(df, expected_freq=expected_freq)
    alert_on_data_quality(quality, source, symbol)

    features = build_feature_vector(df, position_state) if mode == "raw" else build_model_feature_vector(df, position_state)
    if fields:
        features = {k: features[k] for k in fields if k in features}

    return {
        "symbol": symbol, "source": source, "timeframe": timeframe, "mode": mode,
        "feature_count": len(features), "features": features,
        "schema_version": FEATURE_SCHEMA_VERSION, "schema_hash": feature_schema_hash(features),
        "data_quality": quality,
        "disclaimer": DISCLAIMER,
    }


@mcp.tool()
def rl_core_feature_vector(symbol: str, source: str = "crypto", timeframe: str = "1h",
                            count: int = 300, position_state: dict | None = None) -> dict:
    """Wie rl_feature_vector (mode='model'), aber auf 61 handkuratierte Features reduziert -- schlankerer Standard-Einstieg."""
    df = source_router.get_candles(source, symbol, timeframe, count)
    full = build_model_feature_vector(df, position_state)
    core = build_core_feature_vector(full)
    return {
        "symbol": symbol, "source": source, "timeframe": timeframe,
        "feature_count": len(core), "of_total_available": len(full), "features": core,
        "schema_version": FEATURE_SCHEMA_VERSION, "disclaimer": DISCLAIMER,
    }


@mcp.tool()
def check_data_quality(symbol: str, source: str = "crypto", timeframe: str = "1h",
                        count: int = 300, expected_freq: str | None = None) -> dict:
    """Prueft OHLCV auf Luecken/Duplikate/OHLC-Inkonsistenzen/Preisspruenge, ohne Features zu berechnen."""
    df = source_router.get_candles(source, symbol, timeframe, count)
    result = validate_ohlcv(df, expected_freq=expected_freq)
    alert_on_data_quality(result, source, symbol)
    return result


# ---------------------------------------------------------------------------
# Uebergreifend
# ---------------------------------------------------------------------------

@mcp.tool()
def list_rl_feature_categories() -> dict:
    """Feature-Anzahl je Kategorie (raw/model/core)."""
    import numpy as np
    from . import rl_features as rf
    n = 300
    idx = pd.date_range("2024-01-01", periods=n, freq="h")
    price = 100 + np.cumsum(np.random.randn(n))
    df = pd.DataFrame({"open": price, "high": price + 1, "low": price - 1,
                        "close": price, "volume": np.random.randint(100, 1000, n)}, index=idx)
    categories = {
        "preis_returns": rf._price_features(df), "trend_ma": rf._trend_features(df),
        "momentum": rf._momentum_features(df), "volatilitaet": rf._volatility_features(df),
        "volumen": rf._volume_features(df), "breakout": rf._breakout_features(df),
        "pivots": rf._pivot_features(df), "fibonacci": rf._fibonacci_features(df),
        "candlestick": rf._candlestick_features(df), "stop_loss_risiko": rf._risk_features(df),
        "session_zeit": rf._session_features(df), "statistik": rf._statistical_features(df),
        "erweiterte_indikatoren": rf._extended_indicator_features(df),
        "regime_trend": rf._regime_features(df), "positions_state": rf._position_state_features(None),
    }
    result = {k: len(v) for k, v in categories.items()}
    result["gesamt_raw"] = sum(len(v) for v in categories.values())
    result["gesamt_model"] = len(rf.build_model_feature_vector(df))
    result["gesamt_core"] = len(CORE_FEATURE_SET)
    return result


@mcp.tool()
def analyze_feature_correlation(symbol: str, source: str = "crypto", timeframe: str = "1h",
                                 history_points: int = 200, threshold: float = 0.95) -> dict:
    """Findet stark korrelierte Feature-Paare ueber echte Historie (rechenintensiv, Default bewusst klein)."""
    df = source_router.get_candles(source, symbol, timeframe, 210 + history_points)
    rows = [build_model_feature_vector(df.iloc[max(0, i - 210):i + 1]) for i in range(210, len(df))]
    history_df = pd.DataFrame(rows, index=df.index[210:])
    report = correlation_report(history_df, threshold=threshold)
    report["disclaimer"] = DISCLAIMER
    return report


# ---------------------------------------------------------------------------
# Monitoring/Alerting
# ---------------------------------------------------------------------------

@mcp.tool()
def check_connector_health() -> dict:
    """Pingt Crypto.com/Binance/Bybit (Ticker), misst Latenz, meldet Alerts bei Fehlern."""
    results = {
        "crypto_com": health_monitor.check("crypto_com", lambda: crypto_com.get_ticker("BTC_USDT")),
        "binance": health_monitor.check("binance", lambda: binance.get_ticker("BTCUSDT")),
        "bybit": health_monitor.check("bybit", lambda: bybit.get_ticker("BTCUSDT")),
    }
    if not mt5_source.MT5_AVAILABLE:
        results["mt5"] = {"source": "mt5", "status": "unavailable", "note": "MetaTrader5-Paket nicht installiert."}
    return results


@mcp.tool()
def get_source_uptime() -> dict:
    """Erfolgsquote der Health-Checks je Quelle seit Prozessstart (0.0-1.0)."""
    return {name: health_monitor.uptime(name) for name in ("crypto_com", "binance", "bybit")}


@mcp.tool()
def get_recent_alerts(limit: int = 20, level: str | None = None) -> list:
    """Letzte Alerts. level optional: info/warning/critical. ALERT_WEBHOOK_URL env var -> zusaetzlich Slack/Discord."""
    return alert_manager.recent(limit=limit, level=level)


# ---------------------------------------------------------------------------
# News-Filter
# ---------------------------------------------------------------------------

@mcp.tool()
def filtered_news(keywords: list[str] | None = None, hours: float = 48,
                   min_relevance: float = 0.0, only_high_impact: bool = False) -> list[dict]:
    """News aus RSS (CoinDesk/Cointelegraph, kein Key), gefiltert nach Zeitfenster/Keyword/Impact, mit Sentiment (heuristisch)."""
    return get_filtered_news(keywords=keywords, hours=hours, min_relevance=min_relevance, only_high_impact=only_high_impact)


@mcp.tool()
def list_news_feeds() -> dict:
    """Konfigurierte RSS-Feed-URLs."""
    return DEFAULT_FEEDS


# ---------------------------------------------------------------------------
# Chart-Pattern-Erkennung
# ---------------------------------------------------------------------------

@mcp.tool()
def chart_patterns(symbol: str, source: str = "crypto", timeframe: str = "1h",
                    count: int = 200, swing_window: int = 5, min_confidence: float = 0.3) -> dict:
    """Double Top/Bottom, Head & Shoulders (+invers), Dreiecke, Keile -- regelbasiert mit Konfidenz-Score."""
    df = source_router.get_candles(source, symbol, timeframe, count)
    patterns = detect_chart_patterns(df, swing_window=swing_window, min_confidence=min_confidence)
    return {"symbol": symbol, "source": source, "timeframe": timeframe,
            "patterns_found": len(patterns), "patterns": patterns, "disclaimer": DISCLAIMER}


# ---------------------------------------------------------------------------
# Stop-Loss & Trailing (Snapshot-Berechnung, kein Backtest)
# ---------------------------------------------------------------------------

@mcp.tool()
def stop_loss_plan(symbol: str, entry_price: float, side: str, source: str = "crypto",
                    timeframe: str = "1h", count: int = 200, stop_method: str = "atr",
                    atr_mult: float = 1.5, trail_method: str = "chandelier",
                    trail_atr_mult: float = 3.0, r_multiple_tp: float = 2.0) -> dict:
    """Initialer Stop (atr/structure) + Take-Profit (R-Vielfaches) + Trailing-Stop (chandelier/percent). Snapshot, kein Backtest."""
    df = source_router.get_candles(source, symbol, timeframe, count)
    plan = stop_management.compute_stop_plan(
        df, entry_price, side, stop_method=stop_method, atr_mult=atr_mult,
        trail_method=trail_method, trail_atr_mult=trail_atr_mult, r_multiple_tp=r_multiple_tp,
    )
    plan["symbol"] = symbol
    plan["disclaimer"] = DISCLAIMER
    return plan


@mcp.tool()
def update_trailing_stop_level(current_stop: float, proposed_stop: float, side: str) -> dict:
    """Ratchet-Logik: Stop bewegt sich nie gegen die Position (long: nur hoch, short: nur runter)."""
    new_stop = stop_management.update_trailing_stop(current_stop, proposed_stop, side)
    return {"side": side, "previous_stop": current_stop, "proposed_stop": proposed_stop, "new_stop": new_stop}


@mcp.tool()
def breakeven_check(entry_price: float, current_price: float, side: str, current_stop: float,
                     trigger_r_multiple: float = 1.0, initial_risk: float | None = None) -> dict:
    """Prueft, ob der Preis weit genug gelaufen ist, um den Stop auf Breakeven zu verschieben."""
    return stop_management.move_to_breakeven(entry_price, current_price, side, current_stop, trigger_r_multiple, initial_risk)


def main():
    """Entry point fuer den installierten CLI-Befehl."""
    mcp.run()


if __name__ == "__main__":
    main()
