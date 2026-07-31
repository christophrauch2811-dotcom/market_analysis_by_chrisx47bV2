"""
Trading-MCP-Connector
======================
Stellt Claude Code (oder jedem anderen MCP-Client) Marktdaten und eine breite
Indikator-/Signal-Bibliothek aus drei Quellen bereit:

  - Crypto.com  (oeffentliche REST-API, kein Key noetig)
  - TradingView (inoffizielle technische Analyse-Zusammenfassung)
  - MetaTrader5 (nur lokal auf Windows mit laufendem Terminal)

Reiner Lese-/Analyse-Connector. Keine Order-Ausfuehrung.
Keine Anlageberatung -- alle Ausgaben sind rein informativ/technisch.

Start:
    python server.py
"""

from mcp.server.fastmcp import FastMCP
import pandas as pd

from .sources import crypto_com, tradingview, mt5_source
from .indicators import compute_all_indicators, fibonacci_retracement, latest_snapshot
from .rl_features import build_feature_vector
from .regime import detect_regime

mcp = FastMCP("trading-connector")

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
    if source == "mt5":
        df = mt5_source.get_ohlcv(symbol, timeframe, count)
    else:
        df = crypto_com.get_candlestick(symbol, timeframe, count)
    regime = detect_regime(df)
    regime["disclaimer"] = DISCLAIMER
    return {"symbol": symbol, "source": source, "timeframe": timeframe, "regime": regime}


# ---------------------------------------------------------------------------
# RL-Feature-Vektor (100+ Features fuer Reinforcement-Learning-Agenten)
# ---------------------------------------------------------------------------

@mcp.tool()
def rl_feature_vector(symbol: str, source: str = "crypto", timeframe: str = "1h",
                       count: int = 300, position_state: dict | None = None) -> dict:
    """Baut einen 180+ Feature RL-State-Vektor (Trend, Momentum, Volatilitaet,
    Volumen, Breakout, Pivots, Fibonacci, Candlestick-Patterns, Stop-Loss-
    Distanzen, Session-/Zeit-Features, Statistik, optionaler Positions-State).

    source: 'crypto' (Crypto.com) oder 'mt5' (MetaTrader5, nur lokal/Windows)
    position_state: optionales dict mit side/entry_price/current_price/bars_held/
        stop_loss/take_profit/peak_equity/current_equity/consecutive_wins/losses
        -- falls der RL-Agent aktuell eine Position haelt.
    """
    if source == "mt5":
        df = mt5_source.get_ohlcv(symbol, timeframe, count)
    else:
        df = crypto_com.get_candlestick(symbol, timeframe, count)

    features = build_feature_vector(df, position_state)
    return {
        "symbol": symbol, "source": source, "timeframe": timeframe,
        "feature_count": len(features), "features": features,
        "disclaimer": DISCLAIMER,
    }


# ---------------------------------------------------------------------------
# Uebergreifend
# ---------------------------------------------------------------------------

@mcp.tool()
def list_rl_feature_categories() -> dict:
    """Zeigt, wie viele Features rl_feature_vector je Kategorie liefert."""
    import pandas as pd, numpy as np, rl_features as rf
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
    return {k: len(v) for k, v in categories.items()} | {"gesamt": sum(len(v) for v in categories.values())}


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


def main():
    """Entry point für den installierten CLI-Befehl 'trading-connector'."""
    mcp.run()


if __name__ == "__main__":
    main()
