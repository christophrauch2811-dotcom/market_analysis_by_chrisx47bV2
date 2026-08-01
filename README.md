# Market Analysis by chrisx47b

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
pip install git+https://github.com/<dein-username>/market-analysis-by-chrisx47b.git
```

**Lokal aus dem Repo:**

```bash
git clone https://github.com/<dein-username>/market-analysis-by-chrisx47b.git
cd market-analysis-by-chrisx47b
pip install .
```

Beides installiert den CLI-Befehl `market-analysis-by-chrisx47b`.

Auf Windows wird `MetaTrader5` automatisch mitinstalliert (Marker in
`pyproject.toml`, `pip install MetaTrader5` als separater Schritt ist nicht
mehr nötig) -- das MT5-Terminal muss trotzdem installiert und eingeloggt
sein. Auf macOS/Linux wird `MetaTrader5` automatisch übersprungen (kein
Fehler); die MT5-Tools lehnen dort mit einer klaren Fehlermeldung ab statt abzustürzen.

## In Claude Code einbinden

```bash
claude mcp add market-analysis-by-chrisx47b -- market-analysis-by-chrisx47b
```

Danach stehen die Tools in jeder Claude-Code-Session zur Verfuegung, z.B.:

> "Hol mir die 1h-Indikatoren fuer BTC_USDT von Crypto.com"
> "Wie ist das TradingView-Rating fuer XAUUSD auf OANDA im 4h-Chart?"
> "Welches Marktregime hat ETH_USDT gerade auf 4h?"

## Verfuegbare Tools

**26 Tools** (bewusst konsolidiert -- siehe [Kosten/Token-Effizienz](#kostentoken-effizienz) unten).

| Tool | Quelle | Beschreibung |
|---|---|---|
| `candles` | crypto/binance/bybit/mt5/kucoin/kraken/bitfinex/coingecko/yahoo | OHLCV-Kerzen (ein Tool statt neun) |
| `ticker` | crypto/binance/bybit/kucoin/kraken/bitfinex/coingecko/yahoo | Aktueller Preis/24h-Change/Volumen |
| `order_book` | crypto/binance/bybit/kraken/bitfinex | Orderbuch (Bids/Asks) |
| `tradingview_summary` | TradingView | Buy/Sell/Neutral-Rating je Indikator |
| `create_pinescript_indicator` | – | Generiert Pine-Script-v6-Indikator-Code, speichert optional als `.txt` |
| `create_pinescript_strategy` | – | Generiert Pine-Script-v6-Strategie-Code, lauffähig in TradingViews Strategy Tester |
| `mt5_account_info` | MetaTrader5 | Kontostand/Equity/Margin |
| `mt5_open_positions` | MetaTrader5 | Offene Positionen |
| `mt5_max_history` | MetaTrader5 | Bis zu mehrjährige Historie (Ziel 5-6+ Jahre), nur Metadaten |
| `mt5_download_csv` | MetaTrader5 | Wie oben, speichert volle Historie als CSV lokal |
| `market_regime` | crypto/binance/bybit/mt5 | Trend-/Regime-Klassifikation |
| `extended_indicators` | crypto/binance/bybit/mt5 | 39 Indikatoren (Supertrend, TRIX, Vortex, Connors RSI etc.), `fields`-Parameter für gezielte Abfrage |
| `rl_feature_vector` | crypto/binance/bybit/mt5 | RL-Feature-Vektor (183 model / 249 raw), `fields`-Parameter für gezielte Abfrage |
| `rl_core_feature_vector` | crypto/binance/bybit/mt5 | Handkuratiertes Core-Set (61 Features) |
| `check_data_quality` | crypto/binance/bybit/mt5 | Lücken/Duplikate/OHLC-Inkonsistenzen/Preisspünge |
| `analyze_feature_correlation` | crypto/binance/bybit/mt5 | Stark korrelierte Feature-Paare über echte Historie |
| `list_rl_feature_categories` | – | Feature-Anzahl je Kategorie (raw/model/core) |
| `check_connector_health` | crypto/binance/bybit | Health-Check je Quelle, Latenz, Alerts bei Fehlern |
| `get_source_uptime` | – | Erfolgsquote der Health-Checks je Quelle |
| `get_recent_alerts` | – | Letzte Alerts (Datenqualität, Health-Check-Fehler) |
| `filtered_news` | RSS (CoinDesk, Cointelegraph) | News gefiltert nach Zeitfenster/Keyword/Impact, mit Sentiment |
| `list_news_feeds` | – | Konfigurierte RSS-Feed-URLs |
| `chart_patterns` | crypto/binance/bybit/mt5 | Double Top/Bottom, Head & Shoulders, Dreiecke, Keile |
| `stop_loss_plan` | crypto/binance/bybit/mt5 | Initialer Stop + Take-Profit + Trailing-Stop-Level (Snapshot) |
| `update_trailing_stop_level` | – | Ratchet-Logik für laufenden Trailing-Stop |
| `breakeven_check` | – | Prüft Verschiebung auf Breakeven |

### Kosten/Token-Effizienz

Dieser Connector wurde 2x überarbeitet, um Claude-Code-Sessions günstiger zu
machen. Zwei unterschiedliche Kostenquellen, beide adressiert:

1. **Tool-Schema-Overhead** (grösster Hebel): jedes Tool (Name + Beschreibung
   + Parameter-Schema) wird bei **jeder einzelnen Nachricht** in Claude Code
   mitgeschickt, unabhängig davon, ob es genutzt wird. Gemessen:
   ursprünglich 38 Tools ≈ 6.076 Tokens Fixkosten pro Nachricht. Durch
   Konsolidierung (crypto_candles/binance_candles/bybit_candles/mt5_candles →
   ein generisches `candles`-Tool, analog für ticker/order_book, veraltete
   Klassik-Indikator-Tools entfernt) und gekürzte Docstrings: **26 Tools ≈
   3.739 Tokens (-38%)**.
2. **Tool-Antwortgrösse**: `rl_feature_vector` und `extended_indicators`
   akzeptieren jetzt einen optionalen `fields`-Parameter -- nur die
   angefragten Keys werden zurückgegeben. Getestet: bei einer gezielten
   Frage (z.B. nur RSI + ADX) sinkt die Antwortgrösse von `rl_feature_vector`
   um 98,9%, von `extended_indicators` um 94,9%, statt immer den vollen
   Vektor (183 bzw. 39 Keys) zurückzugeben.

**Wichtige Klarstellung**: Caching (`cache.py`) spart **keine** Claude-Tokens
-- das reduziert nur Latenz/API-Last auf der Datenquellen-Seite. Was Claude
tatsächlich Tokens kostet, ist die Grösse der Tool-Definitionen und der
Tool-Antworten, nicht wie schnell die Daten geholt wurden.

**Praktische Faustregel für Claude Code**: für einfache Fragen (aktueller
Preis, ein einzelner Indikator) `ticker`/`extended_indicators` mit `fields`
nutzen statt `rl_feature_vector` ohne Filter -- der volle 183-Feature-Vektor
ist für ML-Trainingsdaten gedacht, nicht für "was ist der RSI gerade".

### 5 weitere Datenquellen: KuCoin, Kraken, Bitfinex, CoinGecko, Yahoo Finance

Wie Binance/Bybit einfach als weitere `source`-Werte in `candles`/`ticker`/
`order_book`/`market_regime`/`extended_indicators`/`rl_feature_vector` etc.
nutzbar -- **keine neuen Tools**, um den Tool-Schema-Overhead nicht wieder
zu erhöhen.

**Symbol-Format ist je Quelle unterschiedlich** (kein einheitliches Format
über alle 9 Quellen hinweg möglich):

| Quelle | Symbol-Beispiel | Besonderheit |
|---|---|---|
| `kucoin` | `BTC-USDT` (mit Bindestrich) | Kline-Antwort hat unübliche Spaltenreihenfolge (close vor high/low) -- verifiziert und korrekt gemappt |
| `kraken` | `XBTUSD` (XBT statt BTC) | Antwort-Key kann vom angefragten Symbol abweichen (`XBTUSD` → `XXBTZUSD`) -- Code nimmt automatisch den ersten Nicht-`last`-Key |
| `bitfinex` | `tBTCUSD` (t-Präfix, wird automatisch ergänzt falls fehlt) | Candles-Antwort hat unübliche Spaltenreihenfolge (close vor high/low) |
| `coingecko` | `bitcoin` (**Coin-ID, kein Trading-Pair!**) | Kein Ticker im klassischen Sinn -- `timeframe` wird nur grob auf `days` übersetzt, CoinGecko bestimmt die Granularität automatisch. **Braucht inzwischen einen kostenlosen Demo-API-Key** (Umgebungsvariable `COINGECKO_API_KEY`, optional -- ohne Key stärker rate-limitiert) |
| `yahoo` | `AAPL`, `EURUSD=X`, `BTC-USD`, `^GSPC` | **Inoffiziell** (Yahoos offizielle API wurde 2017 eingestellt) -- deckt dafür Aktien/ETFs/Indizes/Forex ab, nicht nur Krypto. Kein Orderbuch, kein natives 4h-Intervall |

`order_book` ist für `kucoin`/`coingecko`/`yahoo` nicht angebunden (kein
öffentliches L2-Orderbuch bzw. kein Konzept dafür).

Alle 5 gegen die echte API-Dokumentation verifiziert, mit gemockten,
formatgetreuen Antworten getestet (kein Live-Zugriff aus dieser Sandbox
möglich) -- Live-Verifikation mit echten Daten steht bei dir noch aus.

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
`check_data_quality`, `analyze_feature_correlation` und `chart_patterns`
akzeptieren alle denselben `source`-Parameter (`'crypto'`, `'binance'`,
`'bybit'`, `'mt5'`) -- neue Quellen werden zentral in `source_router.py`
registriert, nicht in jedem Tool einzeln.

### News-Filter (`news_filter.py`)

CryptoCompare (die naheliegende keyless Crypto-News-API) verlangt inzwischen
einen API-Key -- passt nicht zur "kein Key nötig"-Linie der anderen Module.
Stattdessen: offizielle, öffentliche **RSS-Feeds** (CoinDesk, Cointelegraph),
kein API-Key nötig.

- `filtered_news(keywords, hours, min_relevance, only_high_impact)` --
  filtert nach Zeitfenster, Keyword-Relevanz, entfernt Near-Duplicates
  (mehrere Quellen berichten oft fast wortgleich dieselbe Meldung).
- Jeder Treffer bekommt `impact` (`high`/`normal`, Keyword-Liste in
  `HIGH_IMPACT_KEYWORDS`) und `sentiment` (heuristisches Keyword-Sentiment,
  **kein ML-Modell** -- nur ein grober erster Filter).
- **Quellenunabhängig gebaut**: `filter_news()` arbeitet auf einer Liste von
  dicts (`title`/`link`/`published`/`summary`) -- funktioniert genauso mit
  Items aus einer bezahlten News-API oder einem anderen MCP-Connector.
- ⚠️ **Ungetestet mit echten Daten**: Der XML-Parser folgt dem
  Standard-RSS-2.0-Format und wurde gegen ein synthetisches Beispieldokument
  getestet, aber ich konnte die echten Feed-Inhalte aus dieser Sandbox nicht
  abrufen (Netzwerk-Domain nicht freigegeben). Bitte lokal verifizieren.

### Erweiterte Indikatoren (`extended_indicators.py`) -- Abgleich gegen TradingView

TradingView listet öffentlich ~150 echte technische Preis-/Volumen-Indikatoren
(nach Abzug von On-Chain-Metriken, Fundamentaldaten, ETF-Flows etc. --
[Quelle](https://www.tradingview.com/support/folders/43000587405-built-in-indicators/)).
Ein systematischer Abgleich gegen unseren bisherigen Satz ergab ~20 bekannte
Lücken, die hier geschlossen wurden:

- **Aus der `ta`-Bibliothek angebunden**: TRIX, KST, DPO, Vortex Indicator,
  PPO/PVO, Stochastic RSI, ADL, Ease of Movement, NVI, PVT, Mass Index
- **Selbst implementiert** (nicht in `ta` enthalten, Standardformeln):
  Supertrend, Hull Moving Average, VWMA, Chande Momentum Oscillator,
  Chaikin Oscillator, Williams Alligator, Fisher Transform, Connors RSI

Getestet mit synthetischen Trend-Daten: Supertrend erkennt Auf-/Abwärtstrend
korrekt, Hull MA reagiert wie erwartet schneller auf Preisänderungen als ein
klassischer SMA gleicher Länge, alle Wertebereiche (RSI-artige 0-100,
Oszillatoren etc.) plausibel.

**Bewusst nicht abgedeckt**: Chande Kroll Stop, Klinger Oscillator, McGinley
Dynamic, SMI Ergodic, DEMA/TEMA, Woodies CCI, Rob-Booker-Indikatoren, Zig
Zag, Williams Fractal -- Nische/selten genutzt oder inhaltlich redundant mit
der bereits vorhandenen Swing-Erkennung (`chart_patterns.py`). Die 100.000+
Community-Pine-Scripts sind kein fester Standard und kein sinnvoll
erreichbares Ziel.

### Chart-Pattern-Erkennung (`chart_patterns.py`)

Swing-Punkt-basiert (lokale Hoch-/Tiefpunkte über ein Fenster), erkennt:
Double Top/Bottom, Head & Shoulders (+ invers), Ascending/Descending/
Symmetrical Triangle, Rising/Falling Wedge. Jeder Treffer hat einen
`confidence`-Score (Toleranzband bei Doppel-Mustern, R² der Trendlinien bei
Dreiecken/Keilen). **Regelbasiert, kein ML-Modell** -- Chartmuster sind per
Definition fuzzy; als Zusatzsignal gedacht, nicht als alleinige
Handelsgrundlage.

### Stop-Loss & Trailing (`stop_management.py`)

**Reine Level-Berechnung, bewusst kein Backtest/keine P&L-Simulation.**
`stop_loss_plan` liefert einen Snapshot für den aktuellen Zeitpunkt:

- Initialer Stop: ATR-basiert oder Struktur-basiert (letztes Swing-Low/-High)
- Take-Profit: R-Vielfaches des initialen Risikos
- Trailing-Stop: Chandelier Exit (ATR-basiert) oder Prozent-Trailing

Für echtes Nachziehen über Zeit hält der Aufrufer den aktuellen Stop selbst
und ruft bei jedem neuen Preis `update_trailing_stop_level` auf --
Ratchet-Logik stellt sicher, dass sich der Stop nie gegen die Position
bewegt (long: nur nach oben, short: nur nach unten). `breakeven_check` prüft
zusätzlich, ob der Preis weit genug gelaufen ist, um auf Breakeven zu
verschieben.

### Mehrjährige MT5-Historie & CSV-Export (`export.py`)

`mt5_max_history`/`mt5_download_csv` holen historische Kerzen nicht per
einzelnem `copy_rates_from_pos` (das liefert nur die letzten N Kerzen),
sondern in Chunks über `copy_rates_range` -- Ziel sind 5-6+ Jahre.

- **Chunking**: Standardmäßig 180-Tage-Fenster, damit einzelne Mehrjahres-
  Anfragen nicht an Terminal-/Broker-Limits scheitern. Ergebnisse werden
  dedupliziert und chronologisch sortiert.
- **Ehrlich über Verfügbarkeit**: Wie viel Historie tatsächlich existiert,
  entscheidet der Broker -- bei M1 oft nur Monate, bei H1/D1 häufig mehrere
  Jahre. Die Antwort meldet die *tatsächlich* abgedeckte Zeitspanne, statt
  einen Fehler zu werfen, wenn weniger als angefragt verfügbar ist.
- **CSV landet lokal**: Da MT5 nur auf deinem eigenen Windows-Rechner läuft
  (dort, wo der Server gestartet wird), schreibt `mt5_download_csv` die
  Datei direkt auf deine Festplatte -- kein Upload/Download-Umweg. Ohne
  eigenen `output_path` wird automatisch ein Dateiname aus Symbol/Timeframe/
  Zeitstempel im aktuellen Arbeitsverzeichnis erzeugt.
- Getestet mit einem simulierten Broker (3 Jahre Cutoff bei 6 Jahren Anfrage)
  -- Chunking, Deduplizierung und Sortierung funktionieren korrekt; echte
  Live-Verifikation mit deinem Broker steht wie bei den anderen MT5-Funktionen noch aus.

### Pine-Script-Generator (`pinescript_generator.py`)

Generiert **Pine Script v6** (aktuelle Version seit Nov. 2024, kein v7) --
verpflichtende `ta.*`-Namespaces, `input.int()`/`input.float()` statt
generischem `input()`, `if`-Blöcke statt des in v6 entfernten
`when=`-Parameters bei `strategy.entry()`.

- **`create_pinescript_indicator`**: kombiniert beliebig viele Bausteine
  (SMA, EMA, RSI, MACD, Bollinger, ATR, Supertrend, VWAP, ADX, Stochastic) zu
  einem Skript. Mehrfache gleiche Bausteine (z.B. zwei EMAs) bekommen
  automatisch durchnummerierte Variablennamen, damit sie nicht kollidieren.
- **`create_pinescript_strategy`**: vier Entry-Methoden (EMA-Crossover,
  RSI-Reversion, Supertrend-Flip, Donchian-Breakout) × zwei Exit-Methoden
  (prozentual oder ATR-basiert) × long/short/beide -- lauffähig in
  TradingViews eigenem Strategy Tester. **Bewusst delegiert**: dieser
  Connector backtestet nicht selbst (siehe frühere Entscheidung), das hier
  gibt dir stattdessen fertigen Code für TradingViews eigene
  Backtesting-Infrastruktur.

⚠️ **Der generierte Code wurde NICHT compiliert** -- es gibt keinen
Pine-Script-Compiler in dieser Umgebung. Die Syntax folgt den verifizierten
v6-Konventionen und wurde strukturell geprüft (Klammern-Balance, korrekte
Variablennamen bei Mehrfach-Komponenten, alle 10 Indikator-Bausteine und
alle 32 Entry/Exit/Richtungs-Kombinationen der Strategie durchgetestet) --
das ist aber kein Ersatz für eine echte Compilierung.

✅ **Live verifiziert**: sowohl ein generierter Indikator als auch eine
generierte Strategie liefen erfolgreich im echten TradingView Pine-Editor
(Bestätigung erhalten). Trotzdem gilt weiterhin: bei neuen Kombinationen
(andere Bausteine, andere Entry/Exit-Methoden) im Zweifel im Pine-Editor prüfen.

**Datei-Export**: `create_pinescript_indicator`/`create_pinescript_strategy`
speichern den Code standardmäßig (`save_to_file=True`) zusätzlich als
`.txt`-Datei lokal auf der Festplatte (dieser Server läuft auf deinem
Rechner -- kein Upload/Download-Umweg). Ohne eigenen `output_path` wird
automatisch ein Dateiname aus Name/Zeitstempel im aktuellen
Arbeitsverzeichnis erzeugt; der zurückgegebene Datei-Inhalt ist byte-genau
identisch mit dem `pine_script`-Feld der Antwort (getestet).

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
7. ~~Backtesting-Schicht~~ -- **wieder entfernt**: Auf Wunsch macht dieser
   Connector bewusst kein Backtesting/Monte-Carlo mehr. Andere Lastcharakteristik
   (lange, blockierende Läufe statt Millisekunden-Antworten) und andere
   Zuständigkeit (Backtest-Logik ist quellenunabhängig, gehört nicht in einen
   Marktdaten-Connector) -- dafür wäre ein eigener Connector sinnvoller.

**Neu seit der Umbenennung zu "Market Analysis by chrisx47b":**
- News-Filter (`news_filter.py`, RSS statt kostenpflichtiger API)
- Chart-Pattern-Erkennung (`chart_patterns.py`, regelbasiert mit Konfidenz-Score)
- Stop-Loss/Trailing-Berechnung (`stop_management.py`, reine Level-Berechnung, kein Backtest)

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

## Tests, Failover, Persistenz (v0.3.0)

- **Echte Test-Suite**: `pip install -e ".[dev]"` dann `pytest -v` -- 35 Tests,
  alle mit dokumentationsgetreuen Mock-Antworten (kein Netzwerk nötig, läuft
  in CI). Deckt Regressionen ab, die in diesem Projekt bereits real
  aufgetreten sind (Crypto.com-Endpunkt, Bybit-Sortierung, KuCoin/Bitfinex-
  Spaltenreihenfolge, Kraken-Pair-Key).
- **Rate-Limits verifiziert**: alle 8 HTTP-Quellen gegen die jeweils echte
  Dokumentation geprüft und korrigiert (vorher teils 15-24x zu aggressiv
  eingestellt, z.B. Kraken/CoinGecko/Bitfinex).
- **Automatischer Failover**: `candles`/`ticker` akzeptieren einen optionalen
  `fallback_sources`-Parameter (`[{"source": "binance", "symbol": "BTCUSDT"}]`)
  -- wird nacheinander versucht, falls die Primärquelle fehlschlägt. Symbol-
  Format ist je Quelle unterschiedlich, deshalb pro Fallback-Eintrag am
  besten explizit angeben.
- **Persistente Historie**: Health-Checks/Alerts landen zusätzlich in einer
  lokalen JSONL-Datei (`MARKET_ANALYSIS_HISTORY_FILE`, Default im
  Arbeitsverzeichnis) und werden beim Serverstart wieder geladen -- ein
  Neustart löscht die Uptime-Historie nicht mehr.
- **CHANGELOG.md**: Versionshistorie nach Keep-a-Changelog-Format.

## Retry-Verhalten

Alle HTTP-Aufrufe (Crypto.com, Binance, Bybit) haben einen 10s-Timeout und
wiederholen bei transienten Netzwerkfehlern (Timeout, ConnectionError) bis zu
2x mit exponentiellem Backoff (1s, 2s) -- ohne neue Abhängigkeit
(`retry_with_backoff` in `cache.py`, reines Python + `requests`, das schon
Abhängigkeit ist). Nach dem letzten Versuch wird die ursprüngliche Exception
unverändert weitergereicht, nichts wird verschluckt. Getestet: Erfolg nach
mehreren Fehlversuchen sowie korrektes Scheitern nach Erschöpfung aller
Versuche.

**Bewusst nicht umgesetzt** (aus einem externen Review vorgeschlagen, aber
abgelehnt, um den Tool-Umfang/die Komplexität nicht unnötig aufzublähen):
13 zusätzliche Tools (Portfolio-Risiko, Orderbuch-Imbalance, Price-Alerts,
Economic-Calendar etc. -- würden den gerade erst gesenkten
Tool-Schema-Overhead wieder erhöhen), Async-Rewrite (httpx/anyio -- Overkill
für Einzelnutzer-Sessions), volles Pydantic-Layer (FastMCP validiert Typen
bereits), SQLite/Parquet-Persistenz, WebSocket-Bridge, strukturiertes Logging.

## Bekannte Einschraenkungen

- **TradingView** hat keine offizielle Public API. `tradingview-ta` nutzt denselben
  Endpunkt wie das TA-Widget auf tradingview.com — inoffiziell, kann sich jederzeit aendern.
- **MetaTrader5** funktioniert ausschliesslich lokal auf Windows mit laufendem Terminal,
  nicht in einer Cloud-Umgebung.
- Fuer eine oeffentliche Weitergabe (z.B. GitHub) sollten Nutzer eigene API-Keys/Setups
  mitbringen — es sind aktuell keine persoenlichen Zugangsdaten im Code hinterlegt.
