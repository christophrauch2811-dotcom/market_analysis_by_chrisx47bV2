# Trading MCP Connector

Ein MCP-Server, der Claude Code (oder jedem MCP-faehigen Client) Marktdaten und
technische Indikatoren aus drei Quellen bereitstellt:

- **Crypto.com** – oeffentliche REST-API, kein API-Key noetig (Candles, Ticker, Orderbuch)
- **TradingView** – inoffizielle technische Analyse-Zusammenfassung (`tradingview-ta`)
- **MetaTrader5** – nur nutzbar, wenn der Server lokal auf Windows mit laufendem MT5-Terminal gestartet wird

Reiner **Lese-/Analyse-Connector**. Es findet keine Order-Ausfuehrung statt.
Alle Ausgaben sind informativ/technischer Natur, keine Anlageberatung.

## Installation

**Direkt aus GitHub (empfohlen):**

```bash
pip install git+https://github.com/<dein-username>/trading-mcp-connector.git
```

**Lokal aus dem Repo:**

```bash
git clone https://github.com/<dein-username>/trading-mcp-connector.git
cd trading-mcp-connector
pip install .
```

Beides installiert den CLI-Befehl `trading-connector`.

Unter Windows zusaetzlich `pip install "trading-mcp-connector[mt5]"` fuer die
MetaTrader5-Unterstuetzung, plus das MT5-Terminal installiert und eingeloggt lassen.
Auf macOS/Linux werden die MT5-Tools automatisch mit einer klaren Fehlermeldung
abgelehnt statt abzustuerzen.

## In Claude Code einbinden

```bash
claude mcp add trading-connector -- trading-connector
```

Danach stehen die Tools in jeder Claude-Code-Session zur Verfuegung, z.B.:

> "Hol mir die 1h-Indikatoren fuer BTC_USDT von Crypto.com"
> "Wie ist das TradingView-Rating fuer XAUUSD auf OANDA im 4h-Chart?"
> "Welches Marktregime hat ETH_USDT gerade auf 4h?"

## Verfuegbare Tools

| Tool | Quelle | Beschreibung |
|---|---|---|
| `crypto_candles` | Crypto.com | OHLCV-Kerzen |
| `crypto_ticker` | Crypto.com | Aktueller Preis/24h-Change |
| `crypto_order_book` | Crypto.com | Orderbuch |
| `crypto_indicators` | Crypto.com | Voller Indikator-Satz + Fibonacci |
| `tradingview_summary` | TradingView | Buy/Sell/Neutral-Rating je Indikator |
| `mt5_candles` | MetaTrader5 | OHLCV-Kerzen (nur lokal/Windows) |
| `mt5_indicators` | MetaTrader5 | Voller Indikator-Satz + Fibonacci |
| `mt5_account_info` | MetaTrader5 | Kontostand/Equity/Margin |
| `mt5_open_positions` | MetaTrader5 | Offene Positionen |
| `list_available_indicators` | – | Liste aller berechneten Indikatoren |
| `market_regime` | Crypto.com/MT5 | Eigenständige Regime-/Trenderkennung (Trendrichtung/-stärke, Marktstruktur, Volatilitätsregime) |
| `rl_feature_vector` | Crypto.com/MT5 | **210 RL-Features** inkl. Regime/Trend, Breakout, Stop-Loss-Distanzen etc. |
| `list_rl_feature_categories` | – | Anzahl Features je Kategorie |

### Regime-/Trenderkennung (`regime.py`)

Bewusst als **eigenständiges, quellenunabhängiges Modul** gebaut (keine Abhängigkeit
zu `rl_features.py` oder einer bestimmten Datenquelle), damit es direkt in
zukünftige Connectoren importiert werden kann:

```python
from regime import detect_regime
regime = detect_regime(df)  # df = beliebiges OHLCV-DataFrame
```

Liefert:
- **Trendrichtung & -stärke**: ADX, lineare Regression (Steigung + R²), MA-Alignment ("Perfect Order")
- **Marktstruktur**: Higher-Highs/Higher-Lows vs. Lower-Highs/Lower-Lows über Swing-Punkte
- **Trending vs. Mean-Reverting**: Hurst-Exponent (Näherung), Choppiness Index
- **Volatilitätsregime**: perzentil-basiert (instrumentübergreifend ohne feste Schwellen), Bollinger-Squeeze
- **Zusammenfassendes Label**: z.B. `strong_trend_up`, `weak_trend_down`, `ranging_mean_reverting`

⚠️ Der Hurst-Exponent ist eine Näherung auf Preisniveau und kann bei einem
driftlosen Random Walk trotzdem "trendig" wirken — als Zusatzsignal neben
ADX/Choppiness gedacht, nicht isoliert verwenden.

`rl_feature_vector` bindet `regime.py` automatisch als eigene Feature-Kategorie
ein (Rohwerte + numerische One-Hot-Flags wie `regime_direction_up`,
`regime_structure_bullish`), sodass ein RL-Modell die Labels nicht selbst
encodieren muss.

### RL-Feature-Vektor (`rl_features.py`)

Fuer Reinforcement-Learning-Agenten (z.B. das eigene XAUUSD-Modell) liefert
`rl_feature_vector` einen 182-teiligen State-Vektor pro Zeitpunkt:

- **Preis/Returns** (14): Returns/Log-Returns ueber mehrere Fenster, Gap, Kerzenkoerper
- **Trend/MA** (39): SMA/EMA mehrerer Perioden, MACD, ADX/DI, Aroon, Ichimoku, PSAR
- **Momentum** (16): RSI (mehrere Perioden), Stochastic, Williams %R, ROC, CCI, TSI, Awesome/Ultimate Oscillator
- **Volatilitaet** (11): ATR, Bollinger-/Keltner-/Donchian-Breite, realisierte Vola, Ulcer Index
- **Volumen** (10): OBV, VWAP-Abstand, Volumen-Z-Score, MFI, CMF, Force Index
- **Breakout** (23): Donchian-Breakouts (20/50/100), Baelken seit letztem Ausbruch, Range-Expansion, neue Hochs/Tiefs
- **Pivots** (9): Klassische Pivot/R1/R2/S1/S2 + Abstaende
- **Fibonacci** (10): Alle Standard-Retracement-Level + Golden-Zone-Flag
- **Candlestick-Patterns** (12): Doji, Hammer, Shooting Star, Engulfing, Marubozu, Gaps
- **Stop-Loss/Risiko** (12): ATR-basierte SL-Distanzen, Swing-High/Low-Stops, Risk-Reward-Ziele, Volatilitaets-basierte Positionsgroesse
- **Session/Zeit** (10): Handelssession (Asien/London/NY/Overlap), Wochentag, Monatsrand
- **Statistik** (6): Skew/Kurtosis der Returns, Autokorrelation, Z-Score, Perzentil-Rang
- **Positions-State** (10): Optional vom RL-Environment uebergeben (Seite, Bars gehalten, unrealisierter PnL, Abstand zu SL/TP, Drawdown, Gewinn-/Verluststreak)

## Erweiterbarkeit

Neue Indikatoren: in `indicators.py` ergaenzen (die `ta`-Bibliothek deckt
~40 Standardindikatoren ab, siehe https://technical-analysis-library-in-python.readthedocs.io).

Neue Quelle: neues Modul unter `sources/` nach dem Muster von `crypto_com.py` anlegen
und in `server.py` als `@mcp.tool()` einbinden.

## Bekannte Einschraenkungen

- **TradingView** hat keine offizielle Public API. `tradingview-ta` nutzt denselben
  Endpunkt wie das TA-Widget auf tradingview.com — inoffiziell, kann sich jederzeit aendern.
- **MetaTrader5** funktioniert ausschliesslich lokal auf Windows mit laufendem Terminal,
  nicht in einer Cloud-Umgebung.
- Fuer eine oeffentliche Weitergabe (z.B. GitHub) sollten Nutzer eigene API-Keys/Setups
  mitbringen — es sind aktuell keine persoenlichen Zugangsdaten im Code hinterlegt.
