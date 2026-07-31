"""
Inoffizielle Anbindung an TradingViews technische Analyse-Zusammenfassung
ueber das Community-Paket 'tradingview-ta'.

WICHTIG: Es gibt keine offizielle TradingView-API. Dieses Paket fragt denselben
Endpunkt ab, den TradingViews eigenes "Technical Analysis"-Widget im Browser nutzt.
Nutzung auf eigenes Risiko / gemaess TradingViews Nutzungsbedingungen.
"""

from tradingview_ta import TA_Handler, Interval

INTERVAL_MAP = {
    "1m": Interval.INTERVAL_1_MINUTE,
    "5m": Interval.INTERVAL_5_MINUTES,
    "15m": Interval.INTERVAL_15_MINUTES,
    "1h": Interval.INTERVAL_1_HOUR,
    "4h": Interval.INTERVAL_4_HOURS,
    "1d": Interval.INTERVAL_1_DAY,
    "1w": Interval.INTERVAL_1_WEEK,
}


def get_technical_summary(symbol: str, exchange: str, screener: str, interval: str = "1h") -> dict:
    """
    symbol: z.B. 'BTCUSDT', 'XAUUSD', 'EURUSD'
    exchange: z.B. 'BINANCE', 'OANDA', 'FX_IDC'
    screener: 'crypto', 'forex', 'america', 'cfd', etc.
    """
    handler = TA_Handler(
        symbol=symbol,
        exchange=exchange,
        screener=screener,
        interval=INTERVAL_MAP.get(interval, Interval.INTERVAL_1_HOUR),
    )
    analysis = handler.get_analysis()
    return {
        "summary": analysis.summary,          # BUY/SELL/NEUTRAL + Zaehlungen
        "oscillators": analysis.oscillators,   # RSI, Stoch, CCI, etc. inkl. Einzel-Rating
        "moving_averages": analysis.moving_averages,
        "indicators": analysis.indicators,     # Rohwerte aller Indikatoren
    }
