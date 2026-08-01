"""
Market Analysis by chrisx47b
=============================
Stellt Claude Code (oder jedem anderen MCP-Client) Marktdaten und eine breite
Analyse-Bibliothek aus fuenf Quellen bereit:

  - Crypto.com  (oeffentliche REST-API, kein Key noetig)
  - Binance     (oeffentliche REST-API, kein Key noetig)
  - Bybit       (oeffentliche v5 REST-API, kein Key noetig)
  - TradingView (inoffizielle technische Analyse-Zusammenfassung)
  - MetaTrader5 (nur lokal auf Windows mit laufendem Terminal)

Reiner Lese-/Analyse-Connector. Keine Order-Ausfuehrung, kein Backtesting,
keine Monte-Carlo-Simulation (bewusst nicht Teil dieses Connectors).
Keine Anlageberatung -- alle Ausgaben sind rein informativ/technisch.

Start:
    python server.py
"""

from mcp.server.fastmcp import FastMCP
import pandas as pd

from .sources import crypto_com, tradingview, mt5_source, binance, bybit
from . import source_router
from .indicators import compute_all_indicators, fibonacci_retracement, latest_snapshot
from .rl_features import build_feature_vector, build_model_feature_vector, FEATURE_SCHEMA_VERSION, feature_schema_hash
from .regime import detect_regime
from .data_quality import validate_ohlcv
from .feature_selection import correlation_report, build_core_feature_vector, CORE_FEATURE_SET
from .monitoring import alert_manager, health_monitor, alert_on_data_quality
from .news_filter import get_filtered_news, DEFAULT_FEEDS
from .chart_patterns import detect_chart_patterns
from . import stop_management
from .export import export_ohlcv_csv

mcp = FastMCP("market-analysis-by-chrisx47b")

DISCLAIMER = (
    "Hinweis: Diese Daten sind rein informativ/technischer Natur und stellen "
    "keine Anlageberatung dar."
)


# ---------------------------------------------------------------------------
# Crypto.com Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def crypto_candles(symbol: str, timeframe: str = "1h", count: int = 200) -> dict:
    """Holt OHLCV-Kerzen von Crypto.com.

    symbol: z.B. 'BTC_USDT', 'ETH_USDT'
    timeframe: 1m,5m,15m,30m,1h,4h,1d,1w,1M
    """
    df = crypto_com.get_candlestick(symbol, timeframe, count)
    return {"symbol": symbol, "timeframe": timeframe, "candles": df.reset_index().to_dict("records")}


@mcp.tool()
def crypto_ticker(symbol: str) -> dict:
    """Aktueller Ticker (Preis, 24h-Change, Volumen) von Crypto.com."""
    return crypto_com.get_ticker(symbol)


@mcp.tool()
def crypto_order_book(symbol: str, depth: int = 10) -> dict:
    """Orderbuch (Bids/Asks) von Crypto.com."""
    return crypto_com.get_order_book(symbol, depth)


@mcp.tool()
def crypto_indicators(symbol: str, timeframe: str = "1h", count: int = 200) -> dict:
    """Holt Crypto.com-Kerzen und berechnet den vollen Indikator-Satz
    (Trend, Momentum, Volatilitaet, Volumen) plus Fibonacci-Retracement.
    """
    df = crypto_com.get_candlestick(symbol, timeframe, count)
    snapshot = latest_snapshot(df)
    fib = fibonacci_retracement(df)
    return {"symbol": symbol, "timeframe": timeframe, "indicators": snapshot,
            "fibonacci": fib, "disclaimer": DISCLAIMER}


# ---------------------------------------------------------------------------
# Binance Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def binance_candles(symbol: str, timeframe: str = "1h", count: int = 200) -> dict:
    """Holt OHLCV-Kerzen von Binance. symbol z.B. 'BTCUSDT' (kein Unterstrich)."""
    df = binance.get_candlestick(symbol, timeframe, count)
    return {"symbol": symbol, "timeframe": timeframe, "candles": df.reset_index().to_dict("records")}


@mcp.tool()
def binance_ticker(symbol: str) -> dict:
    """24h-Ticker (Preis, Change, Volumen) von Binance."""
    return binance.get_ticker(symbol)


@mcp.tool()
def binance_order_book(symbol: str, depth: int = 100) -> dict:
    """Orderbuch (Bids/Asks) von Binance."""
    return binance.get_order_book(symbol, depth)


@mcp.tool()
def binance_indicators(symbol: str, timeframe: str = "1h", count: int = 200) -> dict:
    """Holt Binance-Kerzen und berechnet den vollen Indikator-Satz + Fibonacci."""
    df = binance.get_candlestick(symbol, timeframe, count)
    snapshot = latest_snapshot(df)
    fib = fibonacci_retracement(df)
    return {"symbol": symbol, "timeframe": timeframe, "indicators": snapshot,
            "fibonacci": fib, "disclaimer": DISCLAIMER}


# ---------------------------------------------------------------------------
# Bybit Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def bybit_candles(symbol: str, timeframe: str = "1h", count: int = 200, category: str = "spot") -> dict:
    """Holt OHLCV-Kerzen von Bybit. category: 'spot', 'linear' (USDT-Perpetuals), 'inverse'."""
    df = bybit.get_candlestick(symbol, timeframe, count, category=category)
    return {"symbol": symbol, "timeframe": timeframe, "category": category,
            "candles": df.reset_index().to_dict("records")}


@mcp.tool()
def bybit_ticker(symbol: str, category: str = "spot") -> dict:
    """Ticker von Bybit."""
    return bybit.get_ticker(symbol, category=category)


@mcp.tool()
def bybit_order_book(symbol: str, depth: int = 50, category: str = "spot") -> dict:
    """Orderbuch (Bids/Asks) von Bybit."""
    return bybit.get_order_book(symbol, depth, category=category)


@mcp.tool()
def bybit_indicators(symbol: str, timeframe: str = "1h", count: int = 200, category: str = "spot") -> dict:
    """Holt Bybit-Kerzen und berechnet den vollen Indikator-Satz + Fibonacci."""
    df = bybit.get_candlestick(symbol, timeframe, count, category=category)
    snapshot = latest_snapshot(df)
    fib = fibonacci_retracement(df)
    return {"symbol": symbol, "timeframe": timeframe, "indicators": snapshot,
            "fibonacci": fib, "disclaimer": DISCLAIMER}


# ---------------------------------------------------------------------------
# TradingView Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def tradingview_summary(symbol: str, exchange: str, screener: str, interval: str = "1h") -> dict:
    """Technische Analyse-Zusammenfassung von TradingView (inoffiziell).

    symbol: z.B. 'BTCUSDT', 'XAUUSD', 'EURUSD'
    exchange: z.B. 'BINANCE', 'OANDA', 'FX_IDC'
    screener: 'crypto', 'forex', 'america', 'cfd'
    interval: 1m,5m,15m,1h,4h,1d,1w
    """
    result = tradingview.get_technical_summary(symbol, exchange, screener, interval)
    result["disclaimer"] = DISCLAIMER
    return result


# ---------------------------------------------------------------------------
# MetaTrader5 Tools (nur lokal auf Windows nutzbar)
# ---------------------------------------------------------------------------

@mcp.tool()
def mt5_candles(symbol: str, timeframe: str = "1h", count: int = 200) -> dict:
    """Holt OHLCV-Kerzen aus dem lokal laufenden MT5-Terminal.
    Funktioniert nur, wenn dieser Server auf Windows mit installiertem/eingeloggtem MT5 laeuft.
    """
    df = mt5_source.get_ohlcv(symbol, timeframe, count)
    return {"symbol": symbol, "timeframe": timeframe, "candles": df.reset_index().to_dict("records")}


@mcp.tool()
def mt5_indicators(symbol: str, timeframe: str = "1h", count: int = 200) -> dict:
    """Holt MT5-Kerzen und berechnet den vollen Indikator-Satz + Fibonacci."""
    df = mt5_source.get_ohlcv(symbol, timeframe, count)
    snapshot = latest_snapshot(df)
    fib = fibonacci_retracement(df)
    return {"symbol": symbol, "timeframe": timeframe, "indicators": snapshot,
            "fibonacci": fib, "disclaimer": DISCLAIMER}


@mcp.tool()
def mt5_account_info() -> dict:
    """Kontoinformationen (Guthaben, Equity, Margin) aus MT5."""
    return mt5_source.get_account_info()


@mcp.tool()
def mt5_open_positions() -> list:
    """Aktuell offene Positionen in MT5."""
    return mt5_source.get_open_positions()


@mcp.tool()
def mt5_max_history(symbol: str, timeframe: str = "1h", years_back: float = 6.0, chunk_days: int = 180) -> dict:
    """Holt so viel historische MT5-Kerzen wie Broker/Terminal fuer `symbol`
    vorhalten, bis zurueck zu `years_back` Jahren (Ziel: 5-6+ Jahre). Wird in
    Chunks abgerufen, da einzelne Mehrjahresabfragen je nach Terminal/Broker
    gekappt werden koennen. Gibt NUR Metadaten zurueck (Zeilenzahl, tatsaechliche
    Datumsspanne) -- fuer die vollen Kerzen: mt5_download_csv.

    Wie viel Historie tatsaechlich verfuegbar ist, haengt vom Broker ab --
    das kann bei M1 deutlich weniger als 6 Jahre sein, bei H1/D1 oft mehr.
    """
    df = mt5_source.get_max_history(symbol, timeframe, years_back, chunk_days)
    span_years = round((df.index.max() - df.index.min()).days / 365.25, 2)
    return {
        "symbol": symbol, "timeframe": timeframe, "requested_years": years_back,
        "row_count": len(df), "date_range": (str(df.index.min()), str(df.index.max())),
        "actual_years_covered": span_years,
        "note": ("Weniger Jahre als angefragt bedeutet, dass der Broker fuer dieses "
                 "Symbol/Timeframe nicht mehr Historie vorhaelt, nicht notwendigerweise einen Fehler."),
    }


@mcp.tool()
def mt5_download_csv(symbol: str, timeframe: str = "1h", years_back: float = 6.0,
                      chunk_days: int = 180, output_path: str | None = None) -> dict:
    """Holt die maximal verfuegbare MT5-Historie (Ziel: `years_back` Jahre)
    und speichert sie als CSV. Da dieser Server nur lokal mit einem laufenden
    MT5-Terminal funktioniert, landet die Datei direkt auf deiner Festplatte --
    kein Upload/Download-Schritt noetig. Ohne `output_path` wird automatisch
    ein Dateiname (Symbol_Timeframe_Zeitstempel.csv) im aktuellen
    Arbeitsverzeichnis des Server-Prozesses erzeugt.
    """
    df = mt5_source.get_max_history(symbol, timeframe, years_back, chunk_days)
    result = export_ohlcv_csv(df, filepath=output_path, symbol=symbol, timeframe=timeframe)
    result["symbol"] = symbol
    result["timeframe"] = timeframe
    result["requested_years"] = years_back
    return result


# ---------------------------------------------------------------------------
# Regime-/Trenderkennung (quellenunabhaengig, fuer alle zukuenftigen Connectoren nutzbar)
# ---------------------------------------------------------------------------

@mcp.tool()
def market_regime(symbol: str, source: str = "crypto", timeframe: str = "1h", count: int = 300) -> dict:
    """Klassifiziert das aktuelle Marktregime: Trendrichtung/-staerke (ADX,
    lineare Regression, MA-Alignment), Marktstruktur (HH/HL vs. LH/LL),
    Trending- vs. Mean-Reverting-Charakter (Hurst, Choppiness Index) und
    Volatilitaetsregime (inkl. Bollinger-Squeeze).
    """
    df = source_router.get_candles(source, symbol, timeframe, count)
    regime = detect_regime(df)
    regime["disclaimer"] = DISCLAIMER
    return {"symbol": symbol, "source": source, "timeframe": timeframe, "regime": regime}


# ---------------------------------------------------------------------------
# RL-Feature-Vektor (100+ Features fuer Reinforcement-Learning-Agenten)
# ---------------------------------------------------------------------------

@mcp.tool()
def rl_feature_vector(symbol: str, source: str = "crypto", timeframe: str = "1h",
                       count: int = 300, position_state: dict | None = None,
                       mode: str = "model", expected_freq: str | None = None) -> dict:
    """Baut den RL-State-Vektor (Trend, Momentum, Volatilitaet, Volumen,
    Breakout, Pivots, Fibonacci, Candlestick-Patterns, Stop-Loss-Distanzen,
    Session-/Zeit-Features, Statistik, Regime, optionaler Positions-State).

    Prueft die Rohdaten vorher auf Qualitaetsprobleme (Luecken, Duplikate,
    unplausible Spruenge) -- bei Problemen wird 'data_quality' im Ergebnis
    gefuellt, die Berechnung laeuft trotzdem weiter (Warnung, kein Abbruch).

    source: 'crypto' (Crypto.com), 'binance', 'bybit' oder 'mt5' (MetaTrader5, nur lokal/Windows)
    mode: 'model' (Standard) liefert nur skaleninvariante Features -- das
        gehoert in den RL-Observation-Space. 'raw' liefert zusaetzlich
        absolute Preisniveaus (sma_20, pivot_point etc.) fuer Menschen/Debugging.
    expected_freq: optionale pandas-Frequenz (z.B. '1h') fuer die Luecken-Pruefung.
    position_state: optionales dict mit side/entry_price/current_price/bars_held/
        stop_loss/take_profit/peak_equity/current_equity/consecutive_wins/losses
        -- falls der RL-Agent aktuell eine Position haelt.
    """
    df = source_router.get_candles(source, symbol, timeframe, count)

    quality = validate_ohlcv(df, expected_freq=expected_freq)
    alert_on_data_quality(quality, source, symbol)

    if mode == "raw":
        features = build_feature_vector(df, position_state)
    else:
        features = build_model_feature_vector(df, position_state)

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
    """Wie rl_feature_vector (mode='model'), aber auf ein handkuratiertes
    Core-Set von ~45 Features reduziert (weniger redundant, z.B. nur RSI-14
    statt RSI-7/14/21). Sinnvoll als schlankerer Startpunkt fuer erstes Training.
    """
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
    """Prueft OHLCV-Rohdaten auf Luecken, Duplikate, OHLC-Inkonsistenzen und
    unplausible Preisspruenge -- ohne Features zu berechnen. Sinnvoll als
    eigenstaendiger Check vor einem RL-Trainingslauf ueber lange Historien.
    """
    df = source_router.get_candles(source, symbol, timeframe, count)
    result = validate_ohlcv(df, expected_freq=expected_freq)
    alert_on_data_quality(result, source, symbol)
    return result


# ---------------------------------------------------------------------------
# Uebergreifend
# ---------------------------------------------------------------------------

@mcp.tool()
def list_rl_feature_categories() -> dict:
    """Zeigt, wie viele Features rl_feature_vector je Kategorie liefert."""
    import pandas as pd, numpy as np
    from . import rl_features as rf
    n = 300
    idx = pd.date_range("2024-01-01", periods=n, freq="h")
    price = 100 + np.cumsum(np.random.randn(n))
    df = pd.DataFrame({"open": price, "high": price + 1, "low": price - 1,
                        "close": price, "volume": np.random.randint(100, 1000, n)}, index=idx)
    categories = {
        "preis_returns": rf._price_features(df),
        "trend_ma": rf._trend_features(df),
        "momentum": rf._momentum_features(df),
        "volatilitaet": rf._volatility_features(df),
        "volumen": rf._volume_features(df),
        "breakout": rf._breakout_features(df),
        "pivots": rf._pivot_features(df),
        "fibonacci": rf._fibonacci_features(df),
        "candlestick": rf._candlestick_features(df),
        "stop_loss_risiko": rf._risk_features(df),
        "session_zeit": rf._session_features(df),
        "statistik": rf._statistical_features(df),
        "regime_trend": rf._regime_features(df),
        "positions_state": rf._position_state_features(None),
    }
    result = {k: len(v) for k, v in categories.items()}
    result["gesamt_raw"] = sum(len(v) for v in categories.values())
    result["gesamt_model"] = len(rf.build_model_feature_vector(df))
    result["gesamt_core"] = len(CORE_FEATURE_SET)
    return result


@mcp.tool()
def analyze_feature_correlation(symbol: str, source: str = "crypto", timeframe: str = "1h",
                                 history_points: int = 200, threshold: float = 0.95) -> dict:
    """Berechnet den Modell-Feature-Vektor an `history_points` aufeinanderfolgenden
    Zeitpunkten und findet Feature-Paare, die staerker als `threshold` korrelieren
    -- Basis fuer eine gezielte Reduktion des 210-Feature-Sets. Rechenintensiv
    (ein Feature-Vektor pro Zeitpunkt), daher Default bewusst klein gehalten.
    """
    df = source_router.get_candles(source, symbol, timeframe, 210 + history_points)

    rows = []
    for i in range(210, len(df)):
        window = df.iloc[max(0, i - 210):i + 1]
        rows.append(build_model_feature_vector(window))
    history_df = pd.DataFrame(rows, index=df.index[210:])
    report = correlation_report(history_df, threshold=threshold)
    report["disclaimer"] = DISCLAIMER
    return report


@mcp.tool()
def list_available_indicators() -> list:
    """Listet alle Indikatoren, die crypto_indicators / mt5_indicators berechnen."""
    return [
        "sma_20", "sma_50", "sma_200", "ema_12", "ema_26",
        "macd", "macd_signal", "macd_diff", "adx", "cci",
        "ichimoku_a", "ichimoku_b", "psar",
        "rsi_14", "stoch_k", "stoch_d", "williams_r", "roc",
        "bb_high", "bb_low", "bb_mid", "atr", "keltner_high", "keltner_low",
        "obv", "vwap", "mfi", "fibonacci_retracement",
    ]


# ---------------------------------------------------------------------------
# Monitoring/Alerting
# ---------------------------------------------------------------------------

@mcp.tool()
def check_connector_health() -> dict:
    """Pingt jede konfigurierte Quelle mit einer leichten Anfrage an (Ticker
    fuer BTC/BTCUSDT) und misst Latenz/Erfolg. Ergebnisse landen zusaetzlich
    in der Health-Historie (siehe get_source_uptime). MT5 wird nur auf
    Verfuegbarkeit des Pakets geprueft, nicht auf eine echte Verbindung
    (das braeuchte ein lokal laufendes Windows-Terminal).
    """
    results = {
        "crypto_com": health_monitor.check("crypto_com", lambda: crypto_com.get_ticker("BTC_USDT")),
        "binance": health_monitor.check("binance", lambda: binance.get_ticker("BTCUSDT")),
        "bybit": health_monitor.check("bybit", lambda: bybit.get_ticker("BTCUSDT")),
    }
    if not mt5_source.MT5_AVAILABLE:
        results["mt5"] = {"source": "mt5", "status": "unavailable",
                           "note": "MetaTrader5-Paket nicht installiert oder nicht auf Windows."}
    return results


@mcp.tool()
def get_source_uptime() -> dict:
    """Anteil erfolgreicher Health-Checks je Quelle seit Prozessstart
    (0.0-1.0), basierend auf der Historie aus check_connector_health.
    """
    return {name: health_monitor.uptime(name) for name in ("crypto_com", "binance", "bybit")}


@mcp.tool()
def get_recent_alerts(limit: int = 20, level: str | None = None) -> list:
    """Zeigt die letzten Alerts (Datenqualitaetsprobleme, Health-Check-
    Fehlschlaege). level optional: 'info', 'warning', 'critical'.
    Wenn die Umgebungsvariable ALERT_WEBHOOK_URL gesetzt ist, gehen
    warning/critical-Alerts zusaetzlich an diesen Webhook (Slack/Discord-kompatibel).
    """
    return alert_manager.recent(limit=limit, level=level)


# ---------------------------------------------------------------------------
# News-Filter
# ---------------------------------------------------------------------------

@mcp.tool()
def filtered_news(keywords: list[str] | None = None, hours: float = 48,
                   min_relevance: float = 0.0, only_high_impact: bool = False) -> list[dict]:
    """Holt Krypto-News aus offiziellen RSS-Feeds (CoinDesk, Cointelegraph --
    keine Anmeldung/API-Key noetig) und filtert nach Zeitfenster, Keyword-
    Relevanz und optional nur High-Impact-Meldungen (Regulierung, Hacks,
    ETF-Entscheidungen etc.). Jeder Treffer bekommt zusaetzlich ein
    heuristisches Sentiment (Keyword-basiert, KEIN ML-Modell).

    keywords: z.B. ['bitcoin', 'btc'] -- ohne Angabe werden alle Meldungen
        durchgelassen (nur Zeitfenster/Impact-Filter greifen).
    """
    return get_filtered_news(keywords=keywords, hours=hours,
                              min_relevance=min_relevance, only_high_impact=only_high_impact)


@mcp.tool()
def list_news_feeds() -> dict:
    """Zeigt die aktuell konfigurierten RSS-Feeds (Quelle -> URL)."""
    return DEFAULT_FEEDS


# ---------------------------------------------------------------------------
# Chart-Pattern-Erkennung
# ---------------------------------------------------------------------------

@mcp.tool()
def chart_patterns(symbol: str, source: str = "crypto", timeframe: str = "1h",
                    count: int = 200, swing_window: int = 5, min_confidence: float = 0.3) -> dict:
    """Erkennt klassische Chartmuster (Double Top/Bottom, Head & Shoulders
    (+invers), Dreiecke, Keile) ueber Swing-Punkt-Geometrie. Regelbasiert mit
    Konfidenz-Score, KEIN ML-Modell -- als Zusatzsignal gedacht, nicht als
    alleinige Handelsgrundlage.
    """
    df = source_router.get_candles(source, symbol, timeframe, count)
    patterns = detect_chart_patterns(df, swing_window=swing_window, min_confidence=min_confidence)
    return {"symbol": symbol, "source": source, "timeframe": timeframe,
            "patterns_found": len(patterns), "patterns": patterns, "disclaimer": DISCLAIMER}


# ---------------------------------------------------------------------------
# Stop-Loss & Trailing (reine Level-Berechnung, kein Backtest)
# ---------------------------------------------------------------------------

@mcp.tool()
def stop_loss_plan(symbol: str, entry_price: float, side: str, source: str = "crypto",
                    timeframe: str = "1h", count: int = 200, stop_method: str = "atr",
                    atr_mult: float = 1.5, trail_method: str = "chandelier",
                    trail_atr_mult: float = 3.0, r_multiple_tp: float = 2.0) -> dict:
    """Berechnet einen Stop-Plan fuer den AKTUELLEN Zeitpunkt: initialer Stop
    (ATR- oder Struktur-basiert), Take-Profit (R-Vielfaches), aktuelles
    Trailing-Stop-Level (Chandelier Exit oder Prozent-Trailing).

    WICHTIG: Snapshot-Berechnung, keine Trade-Simulation. Fuer echtes
    Nachziehen ueber Zeit muss der Aufrufer den Stop selbst zwischenspeichern
    und bei neuen Preisen erneut abrufen (siehe update_trailing_stop).

    side: 'long' oder 'short'. stop_method: 'atr' oder 'structure'.
    trail_method: 'chandelier' oder 'percent'.
    """
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
    """Ratchet-Logik fuer einen bereits laufenden Trailing-Stop: der Stop darf
    sich nie gegen die Position bewegen (long: nur nach oben, short: nur nach
    unten). Der Aufrufer haelt current_stop selbst zwischen den Aufrufen.
    """
    new_stop = stop_management.update_trailing_stop(current_stop, proposed_stop, side)
    return {"side": side, "previous_stop": current_stop, "proposed_stop": proposed_stop, "new_stop": new_stop}


@mcp.tool()
def breakeven_check(entry_price: float, current_price: float, side: str, current_stop: float,
                     trigger_r_multiple: float = 1.0, initial_risk: float | None = None) -> dict:
    """Prueft, ob der Preis genug in Gewinnrichtung gelaufen ist, um den Stop
    auf Breakeven (+kleinem Puffer) zu verschieben, und gibt das neue Level zurueck."""
    return stop_management.move_to_breakeven(
        entry_price, current_price, side, current_stop, trigger_r_multiple, initial_risk,
    )


def main():
    """Entry point für den installierten CLI-Befehl 'trading-connector'."""
    mcp.run()


if __name__ == "__main__":
    main()
