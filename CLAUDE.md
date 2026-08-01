# CLAUDE.md

Kontext für Claude Code in diesem Repo. Kurz halten -- das hier wird nicht
bei jeder Nachricht mitgeschickt wie Tool-Docstrings, aber wird am
Sessionstart gelesen. Ausführliche Begründungen stehen im README, hier nur
das Handlungsrelevante.

## Projekt

MCP-Connector für Claude Code: Marktdaten + Analyse aus Crypto.com, Binance,
Bybit (alle öffentlich, kein API-Key), TradingView (inoffiziell), MetaTrader5
(nur lokal/Windows). **Reiner Lese-/Analyse-Connector** -- bewusst KEIN
Backtesting, KEINE Monte-Carlo-Simulation, KEINE Order-Ausführung. Wenn danach
gefragt wird: das gehört in einen separaten Connector, nicht hierher.

Paketname: `market_analysis_by_chrisx47b` (Repo/PyPI-Name mit Bindestrichen:
`market-analysis-by-chrisx47b`). CLI-Befehl nach `pip install -e .`:
`market-analysis-by-chrisx47b`.

## Architektur

- `server.py` -- alle MCP-Tools (`@mcp.tool()`). **26 Tools, bewusst
  konsolidiert** -- siehe "Kosten/Token-Konventionen" unten, bevor neue Tools
  ergänzt werden.
- `source_router.py` -- zentraler Dispatcher für candles/ticker/order_book
  über alle Quellen. Neue Quelle = hier einen Eintrag ergänzen, nicht jedes
  Tool einzeln anfassen.
- `sources/` -- `crypto_com.py`, `binance.py`, `bybit.py`, `mt5_source.py`,
  `tradingview.py`. Jede mit `@ttl_cache` (aus `cache.py`) und Rate-Limiter.
- `rl_features.py` -- 249 Raw- / 183 Modell-Features (skaleninvariant) für
  RL-Trainingsdaten. `build_model_feature_vector()` ist der Standard-Pfad;
  `ABSOLUTE_PRICE_KEYS` listet alles, was NICHT ins Modell-Set darf (absolute
  Preisniveaus wie `sma_20`, `pivot_point`).
- `extended_indicators.py`, `regime.py`, `chart_patterns.py`,
  `stop_management.py`, `news_filter.py`, `pinescript_generator.py`,
  `data_quality.py`, `monitoring.py`, `feature_selection.py`, `export.py` --
  jeweils eigenständige, quellenunabhängige Module (nehmen ein OHLCV-
  DataFrame, keine Kopplung an eine bestimmte Quelle).

## Setup

```bash
python -m venv venv
venv\Scripts\activate   # Windows; Linux/Mac: source venv/bin/activate
pip install -e .
pip install MetaTrader5  # nur falls MT5 genutzt wird (separater Schritt!)
```

## Testen

Diese Sandbox/CI hat **keinen Zugriff** auf `api.crypto.com`, `binance.com`,
`bybit.com`, `cointelegraph.com` etc. -- Live-Tests laufen nur lokal beim
Nutzer. Für strukturelle Tests ohne Netzwerk: `requests.get` mit einer
`FakeResp`-Klasse monkeypatchen (Beispiele in der Commit-Historie), oder mit
synthetischem OHLCV-DataFrame (`pd.date_range` + `np.cumsum(np.random.randn(n))`)
gegen die reinen Rechen-Module (`rl_features`, `regime`, `chart_patterns`,
`extended_indicators`, `stop_management`) testen -- die brauchen keine Quelle.

Nach JEDER Änderung: frischer `git clone` in ein Temp-Verzeichnis, `pip
install -e .` dort, Import + Tool-Zahl prüfen. Mehrfach in diesem Projekt
Bugs gefunden, die nur bei einer "sauberen" Neuinstallation auffielen (siehe
Fixes unten).

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
6. **MetaTrader5-Paket** ist eine optionale Abhängigkeit (`pip install
   MetaTrader5`, separater Schritt) -- nicht automatisch Teil von `pip
   install -e .`, da es nur auf Windows installierbar ist.

## Kosten/Token-Konventionen (wichtig für neue Tools)

Jedes Tool-Schema (Name + Docstring + Parameter) wird bei **jeder Nachricht**
in Claude Code mitgeschickt, unabhängig von Nutzung. Gemessen: 38 Tools ≈
6.076 Tokens Fixkosten/Nachricht, nach Konsolidierung auf 26 Tools ≈ 3.739
Tokens (-38%). Beim Ergänzen neuer Tools:

- **Docstrings auf 1-3 Zeilen halten.** Begründungen/Verifikations-Notizen
  gehören ins README, nicht in den Docstring.
- **Vor neuem Tool prüfen, ob `source_router.py` reicht** (generisches Tool
  mit `source`-Parameter) statt ein Pro-Quelle-Tool zu duplizieren.
- **Bei Tools mit grossen Rückgabewerten** (>20 Keys) einen optionalen
  `fields: list[str] | None`-Parameter anbieten (siehe `rl_feature_vector`,
  `extended_indicators` als Vorlage).
- Caching (`cache.py`) spart **keine** Claude-Tokens, nur Latenz/API-Last --
  nicht mit Token-Ersparnis verwechseln.

## Sonstige Konventionen

- Neue Datenquellen-Anbindungen (Endpunkt-URL, Feldnamen, Sortierreihenfolge)
  IMMER gegen die echte, aktuelle API-Dokumentation prüfen (`web_search`/
  `web_fetch`), nicht aus dem Training-Wissen raten -- mehrere echte Bugs
  wurden genau so gefunden (siehe oben).
- Pine-Script-Generator (`pinescript_generator.py`): Syntax ist gegen Pine
  Script **v6** gebaut (aktuell seit Nov. 2024). Kann hier nicht compiliert
  werden (kein Pine-Compiler verfügbar) -- Nutzer testet final im TradingView
  Pine-Editor.
- Absolute Preisniveaus (Rohwerte wie `sma_20`, `pivot_point`, `vwap`) NIE ins
  Modell-Feature-Set aufnehmen (generalisieren nicht zwischen Instrumenten
  unterschiedlicher Grössenordnung) -- immer die `*_pct`/Distanz-Variante
  zusätzlich anbieten und den Rohwert zu `ABSOLUTE_PRICE_KEYS` ergänzen.
