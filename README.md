# Market Analysis by chrisx47b

Ein MCP-Server für Claude Code (oder jeden anderen MCP-fähigen Client):
Marktdaten, technische Analyse, News-Filter, Chartmuster-Erkennung,
Stop-Loss-Berechnung und einen Pine-Script-Generator aus **9 Datenquellen**.

Reiner **Lese-/Analyse-Connector**. Keine Order-Ausführung, kein
Backtesting, keine Monte-Carlo-Simulation (bewusste Entscheidungen, siehe
[Bekannte Einschränkungen](#bekannte-einschränkungen)). Alle Ausgaben sind
informativ/technischer Natur, keine Anlageberatung.

## Datenquellen

| Quelle | API-Key nötig? | Symbol-Beispiel | Besonderheit |
|---|---|---|---|
| **Crypto.com** | Nein | `BTC_USDT` | – |
| **Binance** | Nein | `BTCUSDT` | – |
| **Bybit** | Nein | `BTCUSDT` | v5-API, braucht `category` (spot/linear/inverse), Kerzen kommen absteigend sortiert (wird intern umgedreht) |
| **KuCoin** | Nein | `BTC-USDT` (Bindestrich) | Kline-Spaltenreihenfolge hat close vor high/low |
| **Kraken** | Nein | `XBTUSD` (XBT statt BTC) | Antwort-Key kann vom Symbol abweichen (`XBTUSD`→`XXBTZUSD`) |
| **Bitfinex** | Nein | `tBTCUSD` (t-Präfix, wird automatisch ergänzt) | Candle-Spaltenreihenfolge hat close vor high/low |
| **CoinGecko** | Optional (Demo-Key) | `bitcoin` (**Coin-ID, kein Trading-Pair!**) | Kein wählbares Intervall -- Granularität wird aus `days` automatisch bestimmt |
| **Yahoo Finance** | Nein | `AAPL`, `EURUSD=X`, `BTC-USD`, `^GSPC` | **Inoffiziell** (offizielle API 2017 eingestellt) -- deckt Aktien/ETFs/Indizes/Forex ab, nicht nur Krypto |
| **TradingView** | Nein | `BTCUSDT` + `exchange`/`screener` | **Inoffiziell** -- TA-Rating-Zusammenfassung, kein Kerzenzugriff |
| **MetaTrader5** | Nein (lokales Terminal) | Broker-abhängig, z.B. `EURUSD` | Nur lokal auf Windows mit laufendem, eingeloggtem MT5-Terminal |

Alle 8 HTTP-Quellen wurden gegen die jeweils echte API-Dokumentation
verifiziert (nicht aus dem Gedächtnis geraten) und mit dokumentationsgetreuen
Mock-Antworten getestet (`pytest`, siehe unten). Live-Verifikation mit
echten Daten wurde für Crypto.com, Binance, Bybit und MetaTrader5 bestätigt;
bei KuCoin/Kraken/Bitfinex/CoinGecko/Yahoo/TradingView/News-RSS steht sie
noch aus (Netzwerkzugriff aus der Build-Sandbox nicht möglich).

## Installation

**Direkt aus GitHub:**

```bash
pip install git+https://github.com/christophrauch2811-dotcom/market-analysis-by-chrisx47b.git
```

**Lokal aus dem Repo:**

```bash
git clone https://github.com/christophrauch2811-dotcom/market-analysis-by-chrisx47b.git
cd market-analysis-by-chrisx47b
pip install .
```

Beides installiert den CLI-Befehl `market-analysis-by-chrisx47b`.

Auf Windows wird `MetaTrader5` automatisch mitinstalliert (Marker in
`pyproject.toml`) -- das MT5-Terminal muss trotzdem separat installiert und
eingeloggt sein. Auf macOS/Linux wird `MetaTrader5` automatisch übersprungen
(kein Fehler); die MT5-Tools lehnen dort mit einer klaren Fehlermeldung ab
statt abzustürzen.

**Für Tests (optional):**

```bash
pip install -e ".[dev]"
pytest -v
```

## In Claude Code einbinden

```bash
claude mcp add market-analysis-by-chrisx47b -- market-analysis-by-chrisx47b
```

Danach stehen die Tools in jeder Claude-Code-Session zur Verfügung, z.B.:

> "Hol mir die 1h-Kerzen für BTC_USDT von Crypto.com"
> "Wie ist das TradingView-Rating für XAUUSD auf OANDA im 4h-Chart?"
> "Welches Marktregime hat ETH_USDT gerade auf Kraken?"
> "Erstelle eine Pine-Script-Strategie mit Donchian-Breakout"

## Verfügbare Tools

**26 Tools**, bewusst konsolidiert -- die meisten akzeptieren einen
`source`-Parameter statt eines eigenen Tools pro Quelle (siehe
[Kosten/Token-Effizienz](#kostentoken-effizienz)).

| Tool | Quellen | Beschreibung |
|---|---|---|
| `candles` | alle 9 | OHLCV-Kerzen, optionaler `fallback_sources`-Parameter für automatischen Failover |
| `ticker` | crypto/binance/bybit/kucoin/kraken/bitfinex/coingecko/yahoo | Aktueller Preis/24h-Change/Volumen, ebenfalls mit Failover |
| `order_book` | crypto/binance/bybit/kraken/bitfinex | Orderbuch (Bids/Asks) |
| `tradingview_summary` | TradingView | Buy/Sell/Neutral-Rating je Indikator |
| `create_pinescript_indicator` | – | Generiert Pine-Script-v6-Indikator-Code, speichert optional als `.txt` |
| `create_pinescript_strategy` | – | Generiert Pine-Script-v6-Strategie-Code, lauffähig in TradingViews Strategy Tester |
| `mt5_account_info` | MetaTrader5 | Kontostand/Equity/Margin |
| `mt5_open_positions` | MetaTrader5 | Offene Positionen |
| `mt5_max_history` | MetaTrader5 | Bis zu mehrjährige Historie (Ziel 5-6+ Jahre), nur Metadaten |
| `mt5_download_csv` | MetaTrader5 | Wie oben, speichert volle Historie als CSV lokal |
| `market_regime` | alle 9 (die Candle-Quellen) | Trend-/Regime-Klassifikation |
| `extended_indicators` | alle 9 | 39 Indikatoren (Supertrend, TRIX, Vortex, Connors RSI etc.), `fields`-Parameter für gezielte Abfrage |
| `rl_feature_vector` | alle 9 | RL-Feature-Vektor (183 model / 249 raw), `fields`-Parameter für gezielte Abfrage |
| `rl_core_feature_vector` | alle 9 | Handkuratiertes Core-Set (61 Features) |
| `check_data_quality` | alle 9 | Lücken/Duplikate/OHLC-Inkonsistenzen/Preissprünge |
| `analyze_feature_correlation` | alle 9 | Stark korrelierte Feature-Paare über echte Historie |
| `list_rl_feature_categories` | – | Feature-Anzahl je Kategorie (raw/model/core) |
| `check_connector_health` | crypto/binance/bybit | Health-Check je Quelle, Latenz, Alerts bei Fehlern |
| `get_source_uptime` | – | Erfolgsquote der Health-Checks je Quelle (persistiert über Neustarts) |
| `get_recent_alerts` | – | Letzte Alerts (Datenqualität, Health-Check-Fehler) |
| `filtered_news` | RSS (CoinDesk, Cointelegraph) | News gefiltert nach Zeitfenster/Keyword/Impact, mit Sentiment |
| `list_news_feeds` | – | Konfigurierte RSS-Feed-URLs |
| `chart_patterns` | alle 9 | Double Top/Bottom, Head & Shoulders, Dreiecke, Keile |
| `stop_loss_plan` | alle 9 | Initialer Stop + Take-Profit + Trailing-Stop-Level (Snapshot) |
| `update_trailing_stop_level` | – | Ratchet-Logik für laufenden Trailing-Stop |
| `breakeven_check` | – | Prüft Verschiebung auf Breakeven |

"Alle 9" bezieht sich auf die Quellen, die Kerzen liefern (crypto, binance,
bybit, mt5, kucoin, kraken, bitfinex, coingecko, yahoo) -- TradingView liefert
nur sein eigenes Rating, keine rohen Kerzen, daher dort nicht anwendbar.

---

## Architektur-Überblick

```
sources/            9 Datenquellen-Module (crypto_com, binance, bybit, mt5_source,
                    tradingview, kucoin, kraken, bitfinex, coingecko, yahoo)
source_router.py    Zentraler Dispatcher -- neue Quelle = 1 Eintrag hier, nicht
                    in jedem Tool einzeln
cache.py            TTL-Cache, Rate-Limiter, Retry-mit-Backoff (keine neue Abhängigkeit)
monitoring.py       Health-Checks, Alerts, persistente JSONL-Historie
data_quality.py     OHLCV-Plausibilitätsprüfung (Lücken, Duplikate, Sprünge)
indicators.py       Klassische Indikatoren (SMA/EMA/MACD/RSI/Bollinger/ATR/Fibonacci)
extended_indicators.py  39 zusätzliche Indikatoren (Supertrend, TRIX, Connors RSI etc.)
regime.py           Eigenständige Trend-/Regime-Erkennung
chart_patterns.py   Swing-basierte Chartmuster-Erkennung
stop_management.py  Stop-Loss/Take-Profit/Trailing-Berechnung (kein Backtest)
rl_features.py       249 Raw- / 183 Modell-Features für RL-Trainingsdaten
feature_selection.py 61-Feature-Core-Set + Korrelationsanalyse
news_filter.py       RSS-basierter News-Filter mit Relevanz/Impact/Sentiment
pinescript_generator.py  Pine-Script-v6-Codegenerator (Indikatoren + Strategien)
export.py            CSV-/Text-Datei-Export
server.py            Alle 26 MCP-Tools
```

### Kosten/Token-Effizienz

Zwei unterschiedliche Kostenquellen in Claude Code, beide adressiert:

1. **Tool-Schema-Overhead** (größter Hebel): jedes Tool (Name + Beschreibung +
   Parameter-Schema) wird bei **jeder einzelnen Nachricht** mitgeschickt,
   unabhängig davon, ob es genutzt wird. Gemessen: ursprünglich 38 Tools ≈
   6.076 Tokens Fixkosten pro Nachricht. Durch Konsolidierung (z.B.
   `crypto_candles`/`binance_candles`/`bybit_candles`/... → ein generisches
   `candles`-Tool) und gekürzte Docstrings: **26 Tools ≈ 3.739 Tokens (-38%)**,
   trotz seitdem 5 zusätzlicher Datenquellen.
2. **Tool-Antwortgröße**: `rl_feature_vector` und `extended_indicators`
   akzeptieren einen optionalen `fields`-Parameter -- nur angefragte Keys
   werden zurückgegeben. Bei einer gezielten Frage (z.B. nur RSI + ADX) sinkt
   die Antwortgröße von `rl_feature_vector` um 98,9%, von `extended_indicators`
   um 94,9%.

**Klarstellung**: Caching (`cache.py`) spart **keine** Claude-Tokens -- das
reduziert nur Latenz/API-Last auf der Datenquellen-Seite.

**Faustregel**: für einfache Fragen `ticker`/`extended_indicators` mit
`fields` nutzen statt `rl_feature_vector` ohne Filter -- der volle
183-Feature-Vektor ist für ML-Trainingsdaten gedacht.

---

## Modul-Details

### Regime-/Trenderkennung (`regime.py`)

Eigenständig, quellenunabhängig -- direkt in andere Connectoren importierbar:

```python
from market_analysis_by_chrisx47b.regime import detect_regime
regime = detect_regime(df)  # df = beliebiges OHLCV-DataFrame
```

Liefert Trendrichtung/-stärke (ADX, lineare Regression, MA-Alignment),
Marktstruktur (Higher-Highs/Lows vs. Lower-Highs/Lows), Trending- vs.
Mean-Reverting-Charakter (Hurst-Exponent-Näherung, Choppiness Index),
Volatilitätsregime (perzentilbasiert, Bollinger-Squeeze) und ein
zusammenfassendes Label (`strong_trend_up`, `ranging_mean_reverting` etc.).

⚠️ Der Hurst-Exponent ist eine Näherung auf Preisniveau und kann bei einem
driftlosen Random Walk trotzdem "trendig" wirken -- als Zusatzsignal gedacht,
nicht isoliert verwenden.

### RL-Feature-Vektor (`rl_features.py`)

`rl_feature_vector` liefert pro Zeitpunkt:
- **`mode='model'`** (Standard): 183 skaleninvariante Features -- absolute
  Preisniveaus (`sma_20`, `pivot_point`, `vwap` etc.) sind ausgeschlossen
  (`ABSOLUTE_PRICE_KEYS`), weil sie nicht zwischen Instrumenten
  unterschiedlicher Größenordnung generalisieren.
- **`mode='raw'`**: 249 Features inkl. absoluter Preisniveaus, für
  Menschen/Debugging/Dashboards.

Kategorien: Preis/Returns, Trend/MA, Momentum, Volatilität, Volumen,
Breakout, Pivots, Fibonacci, Candlestick-Patterns, Stop-Loss/Risiko,
Session/Zeit, Statistik, erweiterte Indikatoren, Regime/Trend, optionaler
Positions-State (vom RL-Environment übergeben).

- **Schema-Versionierung**: `FEATURE_SCHEMA_VERSION` + `feature_schema_hash()`
  in jeder Antwort -- ändert sich der Hash, hat sich das Feature-Set
  geändert (Signal, ein trainiertes Modell ggf. neu zu trainieren).
- **Core-Set** (`feature_selection.py`): `rl_core_feature_vector` liefert
  ein handkuratiertes 61-Feature-Set mit weniger Redundanz.
  `analyze_feature_correlation` berechnet auf echter Historie, welche
  Features stark korrelieren.

### Erweiterte Indikatoren (`extended_indicators.py`)

TradingView listet ~150 echte technische Preis-/Volumen-Indikatoren. Ein
Abgleich ergab ~20 bekannte Lücken im ursprünglichen Satz, geschlossen durch:
- **Aus der `ta`-Bibliothek angebunden**: TRIX, KST, DPO, Vortex Indicator,
  PPO/PVO, Stochastic RSI, ADL, Ease of Movement, NVI, PVT, Mass Index
- **Selbst implementiert** (Standardformeln, nicht in `ta` enthalten):
  Supertrend, Hull Moving Average, VWMA, Chande Momentum Oscillator,
  Chaikin Oscillator, Williams Alligator, Fisher Transform, Connors RSI

Getestet: Supertrend erkennt Auf-/Abwärtstrend korrekt, Hull MA reagiert
schneller als klassischer SMA, alle Wertebereiche plausibel.

**Bewusst nicht abgedeckt**: Chande Kroll Stop, Klinger Oscillator, McGinley
Dynamic, SMI Ergodic, DEMA/TEMA, Woodies CCI, Zig Zag, Williams Fractal --
Nische oder redundant mit `chart_patterns.py`. Die 100.000+
Community-Pine-Scripts sind kein fester Standard.

### Chart-Pattern-Erkennung (`chart_patterns.py`)

Swing-Punkt-basiert: Double Top/Bottom, Head & Shoulders (+invers),
Ascending/Descending/Symmetrical Triangle, Rising/Falling Wedge. Jeder
Treffer hat einen `confidence`-Score. Regelbasiert, kein ML-Modell --
Chartmuster sind per Definition fuzzy, als Zusatzsignal gedacht.

### Stop-Loss & Trailing (`stop_management.py`)

**Reine Level-Berechnung, kein Backtest/keine P&L-Simulation.**
`stop_loss_plan` liefert einen Snapshot: initialer Stop (ATR- oder
Struktur-basiert), Take-Profit (R-Vielfaches), Trailing-Stop (Chandelier
Exit oder Prozent-Trailing). Für echtes Nachziehen über Zeit hält der
Aufrufer den Stop selbst und ruft `update_trailing_stop_level` auf --
Ratchet-Logik verhindert, dass sich der Stop gegen die Position bewegt.
`breakeven_check` prüft, ob der Preis weit genug für Breakeven gelaufen ist.

### News-Filter (`news_filter.py`)

CryptoCompare verlangt inzwischen einen API-Key -- passt nicht zur
"kein Key nötig"-Linie. Stattdessen: offizielle **RSS-Feeds** (CoinDesk,
Cointelegraph). `filtered_news` filtert nach Zeitfenster/Keyword-Relevanz,
entfernt Near-Duplicates, klassifiziert `impact` (Keyword-Liste) und
`sentiment` (heuristisch, **kein ML-Modell**). Quellenunabhängig gebaut --
`filter_news()` arbeitet auf jeder Liste von `title`/`link`/`published`/
`summary`-dicts, egal woher.

### Pine-Script-Generator (`pinescript_generator.py`)

Generiert **Pine Script v6** (aktuell seit Nov. 2024). `create_pinescript_indicator`
kombiniert Bausteine (SMA/EMA/RSI/MACD/Bollinger/ATR/Supertrend/VWAP/ADX/
Stochastic). `create_pinescript_strategy` bietet 4 Entry-Methoden ×
2 Exit-Methoden × long/short/beide -- lauffähig in TradingViews eigenem
Strategy Tester (dieser Connector backtestet bewusst nicht selbst). Beide
speichern den Code optional zusätzlich als `.txt`-Datei lokal
(`save_to_file=True`, Standard).

✅ **Live verifiziert**: sowohl Indikator als auch Strategie liefen
erfolgreich im echten TradingView Pine-Editor.

### Mehrjährige MT5-Historie & CSV-Export (`export.py`)

`mt5_max_history`/`mt5_download_csv` holen Kerzen in 180-Tage-Chunks über
`copy_rates_range` (Ziel 5-6+ Jahre), dedupliziert und sortiert. Wie viel
Historie tatsächlich existiert, entscheidet der Broker -- die Antwort meldet
die *tatsächlich* abgedeckte Zeitspanne statt einen Fehler zu werfen.
`mt5_download_csv` schreibt die CSV lokal (kein Upload/Download-Umweg, da
MT5 nur auf dem eigenen Rechner läuft).

### Monitoring & Alerting (`monitoring.py`)

- `check_connector_health` pingt Crypto.com/Binance/Bybit, misst Latenz,
  erzeugt bei Fehlschlag automatisch einen `critical`-Alert.
- `get_source_uptime` liefert die Erfolgsquote (0.0-1.0) je Quelle.
- `get_recent_alerts` zeigt die letzten Alerts. `rl_feature_vector`/
  `check_data_quality` melden automatisch einen `warning`-Alert bei
  Datenqualitätsproblemen (Berechnung läuft trotzdem weiter).
- **Persistenz**: jeder Health-Check/Alert landet zusätzlich in einer
  lokalen JSONL-Datei (`MARKET_ANALYSIS_HISTORY_FILE`, Default im
  Arbeitsverzeichnis) und wird beim Serverstart wieder geladen -- ein
  Neustart löscht die Uptime-Historie nicht mehr. Automatische Rotation
  auf die letzten 1000 Zeilen ab 2 MB Dateigröße.
- **Webhook**: `ALERT_WEBHOOK_URL` (Slack/Discord-Incoming-Webhook) --
  `warning`/`critical`-Alerts gehen zusätzlich dorthin.

### Retry- und Rate-Limit-Verhalten (`cache.py`)

Alle HTTP-Aufrufe haben einen 10s-Timeout und wiederholen bei transienten
Fehlern (Timeout, ConnectionError) bis zu 2x mit exponentiellem Backoff
(1s, 2s) -- ohne neue Abhängigkeit. Rate-Limits sind gegen die jeweils echte
Dokumentation verifiziert (u.a. Kraken: 1 Request/Sekunde gemäß Krakens
eigener Empfehlung; CoinGecko: 25/60s gemäß dokumentiertem 30/min-Limit;
Bitfinex: 15/60s gemäß dokumentiertem 10-90/min-Bereich; Binance/Bybit/
KuCoin: konservative Schätzungen, da keine exakten öffentlichen IP-Limits
dokumentiert sind; Yahoo Finance: sehr konservativ, da inoffizielle API ohne
dokumentiertes Limit).

### Automatischer Failover

`candles`/`ticker` akzeptieren einen optionalen `fallback_sources`-Parameter:

```python
fallback_sources=[{"source": "binance", "symbol": "BTCUSDT"}]
```

Wird nacheinander versucht, falls die Primärquelle fehlschlägt (Timeout,
Ausfall, ungültiges Symbol). Symbol-Format ist je Quelle unterschiedlich --
pro Fallback-Eintrag am besten explizit angeben, sonst wird das Symbol der
Primärquelle übernommen (kann bei inkompatiblen Formaten wie Kraken
fehlschlagen und einfach weiter durchfallen).

### Test-Suite (`tests/`)

```bash
pip install -e ".[dev]"
pytest -v
```

35 Tests, alle mit dokumentationsgetreuen Mock-Antworten (kein Netzwerk
nötig, läuft in CI). Deckt Regressionen ab, die in diesem Projekt bereits
real aufgetreten sind: Crypto.com-Ticker-Endpunkt, Bybit-Sortierung,
KuCoin/Bitfinex-Spaltenreihenfolge, Kraken-Pair-Key, Ratchet-Logik,
Feature-Vektor-Größen, Pine-Script-Struktur.

---

## Erweiterbarkeit

**Neue Datenquelle**: neues Modul unter `sources/` nach dem Muster von
`crypto_com.py` anlegen, dann in `source_router.py` einen Eintrag ergänzen
(nicht in jedem Tool einzeln -- siehe dortige Dispatch-Funktionen).

**Neue Indikatoren**: in `indicators.py` oder `extended_indicators.py`
ergänzen. Die `ta`-Bibliothek deckt ~40 Standardindikatoren ab
(siehe https://technical-analysis-library-in-python.readthedocs.io).

**Release-Prozess**: siehe `CHANGELOG.md` (Keep-a-Changelog-Format) und
`CLAUDE.md` (Architektur-Kontext, bekannte Bugs/Fixes, Konventionen für
Claude Code in diesem Repo).

## Bekannte Einschränkungen

- **TradingView & Yahoo Finance** haben keine offizielle Public API --
  beide nutzen inoffizielle Endpunkte, die sich jederzeit ändern können.
- **CoinGecko** braucht seit einiger Zeit einen (kostenlosen) Demo-API-Key
  für zuverlässigen Zugriff (`COINGECKO_API_KEY`, optional -- ohne Key
  stärker rate-limitiert).
- **MetaTrader5** funktioniert ausschließlich lokal auf Windows mit
  laufendem, eingeloggtem Terminal -- nicht in einer Cloud-Umgebung.
- **Kein Backtesting/Monte-Carlo**: bewusste Entscheidung. Andere
  Lastcharakteristik (lange, blockierende Läufe statt Millisekunden-
  Antworten) und andere Zuständigkeit (Backtest-Logik ist quellenunabhängig,
  gehört nicht in einen Marktdaten-Connector) -- dafür wäre ein eigener
  Connector sinnvoller. Der Pine-Script-Generator delegiert Backtesting statt
  dessen an TradingViews eigenen Strategy Tester.
- **Kein automatischer Failover-Beweis unter echtem Stress**: die
  Failover-Logik ist getestet, aber nie unter echter Marktvolatilität oder
  gleichzeitigem Ausfall mehrerer Quellen beobachtet worden.
- Für eine öffentliche Weitergabe sollten Nutzer eigene API-Keys/Setups
  mitbringen -- es sind keine persönlichen Zugangsdaten im Code hinterlegt.
