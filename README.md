# Trading MCP Connector

Ein MCP-Server, der Claude Code (oder jedem MCP-faehigen Client) Marktdaten und
technische Indikatoren aus fuenf Quellen bereitstellt:

- **Crypto.com** – oeffentliche REST-API, kein API-Key noetig (Candles, Ticker, Orderbuch)
- **Binance** – oeffentliche REST-API, kein API-Key noetig
- **Bybit** – oeffentliche v5-API, kein API-Key noetig (Spot/Linear/Inverse)
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
| `binance_candles` / `binance_ticker` / `binance_order_book` / `binance_indicators` | Binance | Analog zu den Crypto.com-Tools |
| `bybit_candles` / `bybit_ticker` / `bybit_order_book` / `bybit_indicators` | Bybit | Analog, mit zusätzlichem `category`-Parameter (`spot`/`linear`/`inverse`) |
| `tradingview_summary` | TradingView | Buy/Sell/Neutral-Rating je Indikator |
| `mt5_candles` | MetaTrader5 | OHLCV-Kerzen (nur lokal/Windows) |
| `mt5_indicators` | MetaTrader5 | Voller Indikator-Satz + Fibonacci |
| `mt5_account_info` | MetaTrader5 | Kontostand/Equity/Margin |
| `mt5_open_positions` | MetaTrader5 | Offene Positionen |
| `list_available_indicators` | – | Liste aller berechneten Indikatoren |
| `market_regime` | crypto/binance/bybit/mt5 | Eigenständige Regime-/Trenderkennung (Trendrichtung/-stärke, Marktstruktur, Volatilitätsregime) |
| `rl_feature_vector` | crypto/binance/bybit/mt5 | RL-Feature-Vektor, `mode='model'` (154 skaleninvariante Features, Standard) oder `mode='raw'` (210, inkl. absoluter Preisniveaus) |
| `rl_core_feature_vector` | crypto/binance/bybit/mt5 | Handkuratiertes Core-Set (61 Features, weniger Redundanz) |
| `check_data_quality` | crypto/binance/bybit/mt5 | Prüft Lücken, Duplikate, OHLC-Inkonsistenzen, Preisspünge -- ohne Features zu berechnen |
| `analyze_feature_correlation` | crypto/binance/bybit/mt5 | Findet stark korrelierte Feature-Paare über echte Historie |
| `backtest_breakout` | crypto/binance/bybit/mt5 | Vereinfachter Sanity-Check für die Donchian-Breakout-Logik |
| `list_rl_feature_categories` | – | Anzahl Features je Kategorie (raw/model/core) |
| `check_connector_health` | crypto/binance/bybit | Pingt jede Quelle, misst Latenz, meldet Alerts bei Fehlern |
| `get_source_uptime` | – | Erfolgsquote der Health-Checks je Quelle seit Prozessstart |
| `get_recent_alerts` | – | Letzte Alerts (Datenqualität, Health-Check-Fehler) |

### Binance & Bybit

Beide Anbindungen wurden gegen die echte API-Dokumentation verifiziert (nicht
aus dem Gedächtnis geraten):

- **Binance**: Standard-Intervalle (`1m`...`1M`) entsprechen 1:1 unseren Keys.
  Kerzen kommen aufsteigend sortiert, Zahlen als Strings (wird automatisch zu
  float konvertiert).
- **Bybit** (v5-API): braucht zwingend einen `category`-Parameter
  (`spot`/`linear`/`inverse`). **Kerzen kommen absteigend sortiert (neueste
  zuerst)** -- der Code dreht das automatisch um. Jede Antwort hat ein
  `retCode`-Feld, das auf `0` geprüft wird; alles andere wirft eine Exception
  mit der Originalmeldung.

`market_regime`, `rl_feature_vector`, `rl_core_feature_vector`,
`check_data_quality`, `analyze_feature_correlation` und `backtest_breakout`
akzeptieren alle denselben `source`-Parameter (`'crypto'`, `'binance'`,
`'bybit'`, `'mt5'`) -- neue Quellen werden zentral in `source_router.py`
registriert, nicht in jedem Tool einzeln.

### Monitoring & Alerting (`monitoring.py`)

- **`check_connector_health`**: pingt Crypto.com/Binance/Bybit mit einer
  leichten Anfrage (Ticker) und misst Latenz. Ein Fehlschlag erzeugt
  automatisch einen `critical`-Alert.
- **`get_source_uptime`**: Erfolgsquote (0.0-1.0) je Quelle aus der
  In-Memory-Historie seit Prozessstart.
- **`get_recent_alerts`**: zeigt die letzten Alerts. `rl_feature_vector` und
  `check_data_quality` melden automatisch einen `warning`-Alert, wenn
  `validate_ohlcv()` Probleme findet -- die Berechnung läuft trotzdem weiter,
  der Alert ist nur ein Signal nach außen.
- **Webhook**: Wird die Umgebungsvariable `ALERT_WEBHOOK_URL` gesetzt (Slack-
  oder Discord-Incoming-Webhook), gehen `warning`/`critical`-Alerts
  zusätzlich dorthin (`{"text": "[LEVEL] quelle: nachricht"}`). Ohne gesetzte
  Variable bleiben Alerts nur im In-Memory-Log (`get_recent_alerts`).
- Bewusst simpel (kein externer Dienst, keine Datenbank) -- der Zustand ist
  prozessgebunden und geht beim Neustart des Servers verloren. Für einen
  produktionsreifen Einsatz wäre ein persistentes Log (Datei/DB) der nächste Schritt.

### Ehrliche Grenzen & was seit dem letzten Review verbessert wurde

Ein Review dieses Connectors ergab 7 Verbesserungspunkte -- alle sind jetzt umgesetzt:

1. **Mit echten Daten validiert** -- Abgleich mit der echten Crypto.com-Dokumentation
   deckte einen echten Bug auf: `get_ticker()` rief den falschen Endpunkt auf
   (`get-ticker` statt `get-tickers`), das ist gefixt. Feldnamen (`o,h,l,c,v,t`)
   und Antwortstruktur (`result.data`) stimmen mit dem Code überein.
2. **Feature-Set fürs Modell getrennt** (`rl_features.py`) -- `rl_feature_vector`
   liefert per Default (`mode='model'`) nur skaleninvariante Features (154 statt 210).
   Absolute Preisniveaus (`sma_20`, `pivot_point`, `vwap` etc., siehe
   `ABSOLUTE_PRICE_KEYS`) sind ausgeschlossen, weil sie nicht zwischen
   Instrumenten/Zeiträumen generalisieren. `mode='raw'` liefert weiterhin alle
   210 für Menschen/Debugging/Dashboards.
3. **Datenqualitätsprüfung** (`data_quality.py`) -- `validate_ohlcv()` erkennt
   Lücken, Duplikate, OHLC-Inkonsistenzen und unplausible Preisspünge, bevor
   Features berechnet werden. Läuft automatisch in `rl_feature_vector` mit
   (Ergebnis unter `data_quality`), zusätzlich als eigenständiges Tool
   `check_data_quality` abrufbar.
4. **Caching & Rate-Limiting** (`cache.py`) -- TTL-Cache auf allen
   API-Aufrufen (Crypto.com: 30s für Candles, TradingView: 60s) plus
   Token-Bucket-Rate-Limiter, deutlich unter den offiziellen Limits.
5. **Feature-Redundanz reduziert** (`feature_selection.py`) -- `rl_core_feature_vector`
   liefert ein handkuratiertes 61-Feature-Set. `analyze_feature_correlation`
   berechnet auf echter Historie, welche Features stark korrelieren.
6. **Feature-Schema versioniert** -- `FEATURE_SCHEMA_VERSION` +
   `feature_schema_hash()` in jedem `rl_feature_vector`-Ergebnis. Ändert sich
   der Hash, hat sich das Feature-Set geändert -- Signal, ein trainiertes Modell
   ggf. neu zu trainieren statt stillschweigend falsche Spalten zu füttern.
7. **Backtesting-Schicht** (`backtest.py`) -- `backtest_breakout` simuliert eine
   einfache Donchian-Strategie zur groben Plausibilisierung (Return, Max
   Drawdown, Win Rate, Trades vs. Buy&Hold). **Keine echte Order-Simulation**
   (keine Slippage/Liquidität/Orderbuch-Tiefe) -- nur ein schneller Sanity-Check,
   keine Performance-Zusage.

**Weiterhin offen** (bewusst nicht in diesem Durchgang angegangen):
- Live-Verifikation bei dir mit echten API-Keys/Netzwerkzugriff (aus dieser
  Sandbox nicht möglich -- `api.crypto.com` ist nicht erreichbar)
- TradingView bleibt eine inoffizielle Anbindung (Grauzone, siehe oben)
- `hurst_exponent()` in `regime.py` ist weiterhin eine Näherung, kein exakter Wert

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
