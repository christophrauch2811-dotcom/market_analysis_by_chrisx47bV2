# CLAUDE.md

Kontext für Claude Code in diesem Repo. Kurz halten -- das hier wird nicht
bei jeder Nachricht mitgeschickt wie Tool-Docstrings, aber wird am
Sessionstart gelesen. Ausführliche Begründungen stehen im README, hier nur
das Handlungsrelevante.

## Projekt

MCP-Connector für Claude Code: Marktdaten + Analyse aus 9 Quellen (Crypto.com,
Binance, Bybit, KuCoin, Kraken, Bitfinex -- alle öffentlich, kein API-Key;
CoinGecko -- optionaler Key; TradingView, Yahoo Finance -- inoffiziell;
MetaTrader5 -- nur lokal/Windows). **Reiner Lese-/Analyse-Connector** --
bewusst KEIN Backtesting, KEINE Monte-Carlo-Simulation, KEINE
Order-Ausführung. Wenn danach gefragt wird: das gehört in einen separaten
Connector, nicht hierher.

Paketname: `market_analysis_by_chrisx47b` (Repo/PyPI-Name mit Bindestrichen:
`market-analysis-by-chrisx47b`). CLI-Befehl nach `pip install -e .`:
`market-analysis-by-chrisx47b`. Aktuelle Version: siehe `pyproject.toml`
und `CHANGELOG.md`.

## Architektur

- `server.py` -- alle MCP-Tools (`@mcp.tool()`). **26 Tools, bewusst
  konsolidiert** -- siehe "Kosten/Token-Konventionen" unten, bevor neue Tools
  ergänzt werden.
- `source_router.py` -- zentraler Dispatcher für candles/ticker/order_book
  über alle Quellen. Neue Quelle = hier einen Eintrag ergänzen, nicht jedes
  Tool einzeln anfassen. `candles`/`ticker` in `server.py` haben zusätzlich
  einen `fallback_sources`-Parameter für automatischen Failover (kein
  eigenes Tool dafür).
- `sources/` -- `crypto_com.py`, `binance.py`, `bybit.py`, `mt5_source.py`,
  `tradingview.py`, `kucoin.py`, `kraken.py`, `bitfinex.py`, `coingecko.py`,
  `yahoo.py`. Jede mit `@ttl_cache` + Rate-Limiter + `retry_with_backoff`
  (alle aus `cache.py`). **9 Quellen insgesamt** -- alle über
  `source_router.py`, KEINE eigenen Tools pro Quelle (Tool-Anzahl bleibt bei 26).
- `rl_features.py` -- 249 Raw- / 183 Modell-Features (skaleninvariant) für
  RL-Trainingsdaten. `build_model_feature_vector()` ist der Standard-Pfad;
  `ABSOLUTE_PRICE_KEYS` listet alles, was NICHT ins Modell-Set darf (absolute
  Preisniveaus wie `sma_20`, `pivot_point`).
- `extended_indicators.py`, `regime.py`, `chart_patterns.py`,
  `stop_management.py`, `news_filter.py`, `pinescript_generator.py`,
  `data_quality.py`, `monitoring.py`, `feature_selection.py`, `export.py` --
  jeweils eigenständige, quellenunabhängige Module (nehmen ein OHLCV-
  DataFrame, keine Kopplung an eine bestimmte Quelle).
- `monitoring.py` -- Health-Checks/Alerts jetzt PERSISTENT (JSONL-Datei,
  Pfad via `MARKET_ANALYSIS_HISTORY_FILE`, Default im Arbeitsverzeichnis).
  Datei ist in `.gitignore` -- niemals versehentlich committen.
- `tests/` -- pytest-Suite (35 Tests), siehe "Testen" unten.
- `CHANGELOG.md` -- Versionshistorie, Keep-a-Changelog-Format.

## Setup

```bash
python -m venv venv
venv\Scripts\activate   # Windows; Linux/Mac: source venv/bin/activate
pip install -e ".[dev]"   # [dev] fuer pytest, sonst reicht pip install -e .
# MetaTrader5 wird auf Windows automatisch mitinstalliert (Marker in
# pyproject.toml), auf Linux/Mac automatisch uebersprungen -- kein separater Schritt.
```

## Testen

**Echte pytest-Suite vorhanden** (`tests/`, 35 Tests): `pytest -v`. Laeuft
komplett ohne Netzwerk -- Diese Sandbox/CI hat **keinen Zugriff** auf
`api.crypto.com`, `binance.com`, `bybit.com`, `cointelegraph.com` etc.,
deshalb ausschliesslich Mock-basiert:
- `requests.get` mit `FakeResp`/`monkeypatch` fuer alle Quellen-Module
  (Vorlagen in `tests/test_sources.py` und `tests/conftest.py`)
- Synthetisches OHLCV-DataFrame (`tests/conftest.py::synthetic_ohlcv`-Fixture)
  fuer die reinen Rechen-Module (`rl_features`, `regime`, `chart_patterns`,
  `extended_indicators`, `stop_management`, `data_quality`)

**Neue Tests immer ergaenzen**, wenn ein neues Modul/eine neue Quelle
dazukommt -- nicht nur ad-hoc im Chat testen und wieder verwerfen (das ist
frueher mehrfach passiert, siehe Bug 9 unten: Mock-Antworten wurden mehrfach
neu erfunden statt einmal in `tests/` zu verankern).

Nach JEDER Änderung: frischer `git clone` in ein Temp-Verzeichnis, `pip
install -e ".[dev]"` dort, `pytest -v` + Import/Tool-Zahl pruefen. Mehrfach
in diesem Projekt Bugs gefunden, die nur bei einer "sauberen" Neuinstallation
auffielen (siehe Fixes unten).

## Bereits gefundene und gefixte Bugs (nicht wiederholen)

1. **Crypto.com Ticker-Endpoint**: `public/get-ticker` existiert nicht, korrekt
   ist `public/get-tickers` (Plural). Beim Hinzufügen neuer Crypto.com-
   Endpunkte immer gegen die echte Doku prüfen, nicht aus dem Gedächtnis.
2. **`mcp`-Paket-Version**: `mcp>=2.0` hat `FastMCP` entfernt/umbenannt zu
   `MCPServer` -- Dependency ist auf `mcp>=1.0.0,<2` gepinnt
   (`pyproject.toml`). NICHT die Obergrenze entfernen, sonst bricht der
   Import mit `ModuleNotFoundError: No module named 'mcp.server.fastmcp'`.
3. **Bybit-Kerzen-Reihenfolge**: Bybit liefert Kerzen **absteigend** sortiert
   (neueste zuerst), alle anderen Quellen aufsteigend. `sources/bybit.py`
   dreht das nach dem Parsen um (`sort_index()`). Bei neuen Bybit-Endpunkten
   diese Eigenheit im Hinterkopf behalten.
4. **ZIP-Verschachtelung**: Bei Neuverpackung des Repos IMMER in ein frisches
   Temp-Verzeichnis kopieren (nicht in einen bereits existierenden
   Output-Ordner), sonst entsteht `paket/paket/pyproject.toml` durch
   unvollständig gelöschte alte Inhalte. Vor jedem Zip: `unzip -l ... | grep
   pyproject.toml` prüfen -- muss genau einmal auf oberster Ebene erscheinen.
5. **CORE_FEATURE_SET enthielt `macd_diff`**, das aber in
   `ABSOLUTE_PRICE_KEYS` ausgeschlossen ist (absolutes Preisniveau) -- ersetzt
   durch `macd_bull_cross` (skaleninvariant). Beim Ergänzen von Features zu
   `CORE_FEATURE_SET` immer gegen `ABSOLUTE_PRICE_KEYS` prüfen.
6. **MetaTrader5-Paket** war urspruenglich eine optionale Extra-Abhaengigkeit
   (`pip install ".[mt5]"` noetig) -- das fuehrte dazu, dass es bei jeder
   Neuinstallation vergessen wurde. Jetzt in den Hauptabhaengigkeiten mit
   Windows-Marker (`MetaTrader5>=5.0.45; platform_system=='Windows'`) --
   `pip install -e .` installiert es auf Windows automatisch, auf Linux/Mac
   wird es automatisch uebersprungen (kein Fehler).
7. **KuCoin/Bitfinex Kline-Spaltenreihenfolge**: beide liefern `close` VOR
   `high`/`low` in der Antwort (nicht die uebliche open/high/low/close-
   Reihenfolge) -- beim Hinzufuegen neuer Endpunkte dieser beiden Quellen
   immer die tatsaechliche Spaltenreihenfolge aus der Doku pruefen, nicht annehmen.
8. **Kraken-Antwort-Key weicht vom angefragten Symbol ab** (z.B. angefragt
   `XBTUSD`, Antwort-Key `XXBTZUSD`) -- `_first_pair_key()` in `kraken.py`
   nimmt deshalb den ersten Key ungleich `last`, nie den angefragten Namen direkt.
9. **Rate-Limits waren geschaetzt statt verifiziert** -- teils bis zu 24x zu
   aggressiv (Kraken 15/s statt der von Kraken selbst empfohlenen ~1/s,
   CoinGecko 5/s statt dokumentierter 30/min, Bitfinex 10/s statt
   dokumentierter 10-90/min). Bei JEDER neuen Quelle: Rate-Limit-Wert gegen
   die echte Doku suchen, nicht schaetzen -- auch wenn kein Fehler auftritt,
   ist ein zu aggressiver Limiter ein stilles Risiko (IP-Bans, 429er im Dauerbetrieb).
10. **Dokumentations-Drift bei inkrementellen README-Edits**: nach mehreren
    Feature-Erweiterungen standen im README noch alte Zahlen (154/182/210
    Features statt aktuell 183/249, "fünf Quellen" statt 9) -- entstanden,
    weil einzelne Abschnitte unabhängig voneinander bearbeitet wurden. Nach
    JEDER Änderung an Kennzahlen (Feature-Count, Tool-Count, Quellen-Count):
    `grep` das gesamte README nach den alten Zahlen, nicht nur den gerade
    bearbeiteten Abschnitt reparieren.
11. **`market_analysis_history.jsonl`** (persistente Monitoring-Historie,
    siehe `monitoring.py`) ist bewusst in `.gitignore` -- das ist Laufzeit-
    Zustand, kein Code. Beim Verpacken/Committen darauf achten, dass sie
    nicht versehentlich mit reinrutscht.

## Kosten/Token-Konventionen (wichtig für neue Tools)

Jedes Tool-Schema (Name + Docstring + Parameter) wird bei **jeder Nachricht**
in Claude Code mitgeschickt, unabhängig von Nutzung. Gemessen: 38 Tools ≈
6.076 Tokens Fixkosten/Nachricht, nach Konsolidierung auf 26 Tools ≈ 3.739
Tokens (-38%) -- trotz seitdem 5 zusätzlicher Datenquellen. Beim Ergänzen
neuer Tools:

- **Docstrings auf 1-3 Zeilen halten.** Begründungen/Verifikations-Notizen
  gehören ins README, nicht in den Docstring.
- **Vor neuem Tool prüfen, ob `source_router.py` reicht** (generisches Tool
  mit `source`-Parameter) statt ein Pro-Quelle-Tool zu duplizieren. Das war
  der Weg, wie 5 zusätzliche Quellen ohne einen einzigen zusätzlichen Tool-
  Eintrag integriert wurden (siehe KuCoin/Kraken/Bitfinex/CoinGecko/Yahoo).
- **Bei Tools mit grossen Rückgabewerten** (>20 Keys) einen optionalen
  `fields: list[str] | None`-Parameter anbieten (siehe `rl_feature_vector`,
  `extended_indicators` als Vorlage).
- Caching (`cache.py`) spart **keine** Claude-Tokens, nur Latenz/API-Last --
  nicht mit Token-Ersparnis verwechseln.
- Neue Faehigkeit als optionaler Parameter statt neues Tool, wo moeglich
  (siehe `fallback_sources` bei `candles`/`ticker` -- Failover ohne neues Tool).

## Release-Prozess

Bei jeder Aenderung, die mehr als einen kleinen Bugfix darstellt:
1. `CHANGELOG.md` ergaenzen (Hinzugefuegt/Geaendert/Entfernt/Behoben, siehe bestehende Eintraege als Vorlage).
2. Version in `pyproject.toml` anheben (`version = "X.Y.Z"`) -- Semantic Versioning,
   solange < 1.0.0 sind Breaking Changes auch in Minor-Releases ok.
3. Nach dem Commit: `git tag vX.Y.Z && git push --tags` (lokal taggen, Push ist Sache des Nutzers).
4. pytest-Suite MUSS vor jedem Release grün sein (`pytest -v`, siehe "Testen" oben).
5. README auf Konsistenz pruefen (siehe Bug 10) -- besonders Feature-/Tool-/Quellen-Zahlen.

## Sonstige Konventionen

- Neue Datenquellen-Anbindungen (Endpunkt-URL, Feldnamen, Sortierreihenfolge,
  Rate-Limits) IMMER gegen die echte, aktuelle API-Dokumentation prüfen
  (`web_search`/`web_fetch`), nicht aus dem Training-Wissen raten -- mehrere
  echte Bugs wurden genau so gefunden (siehe Bugs 1, 3, 7, 8, 9 oben).
- Pine-Script-Generator (`pinescript_generator.py`): Syntax ist gegen Pine
  Script **v6** gebaut (aktuell seit Nov. 2024). Kann hier nicht compiliert
  werden (kein Pine-Compiler verfügbar) -- Nutzer testet final im TradingView
  Pine-Editor (bereits erfolgreich verifiziert für Indikator + Strategie).
- Absolute Preisniveaus (Rohwerte wie `sma_20`, `pivot_point`, `vwap`) NIE ins
  Modell-Feature-Set aufnehmen (generalisieren nicht zwischen Instrumenten
  unterschiedlicher Grössenordnung) -- immer die `*_pct`/Distanz-Variante
  zusätzlich anbieten und den Rohwert zu `ABSOLUTE_PRICE_KEYS` ergänzen.
- CoinGecko braucht einen optionalen Demo-API-Key (`COINGECKO_API_KEY`),
  Yahoo Finance und TradingView sind inoffizielle APIs -- bei allen dreien
  im Zweifel großzügiger Retry/Fallback statt harter Fehlerbehandlung.
