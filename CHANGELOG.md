# Changelog

Format angelehnt an [Keep a Changelog](https://keepachangelog.com/), Versionierung nach
[Semantic Versioning](https://semver.org/) (solange < 1.0.0: Breaking Changes auch in Minor-Releases möglich).

## [0.3.0] - 2026-08-01

### Hinzugefügt
- 5 weitere Datenquellen: KuCoin, Kraken, Bitfinex, CoinGecko, Yahoo Finance (9 insgesamt) --
  keine neuen Tools, alle über `source_router.py` als weitere `source`-Werte
- Automatischer Failover zwischen Quellen (`fallback_sources`-Parameter bei `candles`/`ticker`)
- Persistente Health-/Alert-Historie (JSONL-Datei, überlebt einen Server-Neustart)
- Echte pytest-Suite (35 Tests) mit dokumentationsgetreuen Mock-Antworten für alle 9 Quellen
- Pine-Script-v6-Generator (Indikatoren + Strategien), live im TradingView-Editor verifiziert
- 39 erweiterte Indikatoren (Supertrend, TRIX, Vortex, Connors RSI, Fisher Transform etc.)
- News-Filter (RSS, kein API-Key), Chart-Pattern-Erkennung, Stop-Loss/Trailing-Berechnung
- Mehrjährige MT5-Historie (Chunking, Ziel 5-6+ Jahre) + CSV-Export
- Monitoring/Alerting (Health-Checks, optionaler Slack/Discord-Webhook)
- Retry-Logik mit Exponential-Backoff für alle HTTP-Quellen
- `pyproject.toml`-Metadaten für PyPI (Classifiers, Keywords, URLs)

### Geändert
- Umbenennung von `trading-mcp-connector` zu `market-analysis-by-chrisx47b`
- 38 → 26 Tools (Konsolidierung von Pro-Quelle-Tools zu generischen `candles`/`ticker`/`order_book`)
  -- Tool-Schema-Overhead dadurch ~38% geringer
- `rl_feature_vector`/`extended_indicators`: optionaler `fields`-Parameter für gezielte Abfragen
- MetaTrader5 von optionaler Extra-Abhängigkeit in Hauptabhängigkeiten verschoben (Windows-Marker)
- Rate-Limits aller Quellen gegen echte Dokumentation verifiziert und korrigiert
  (u.a. Kraken 15/s → 1/s, CoinGecko 5/s → 0,4/s, Bitfinex 10/s → 0,25/s)

### Entfernt
- Backtesting/Monte-Carlo-Funktionalität (bewusst nicht Teil dieses Connectors)
- Veraltete Klassik-Indikator-Tools (`crypto_indicators` etc., `list_available_indicators`)
  -- redundant mit `extended_indicators`/`rl_core_feature_vector`

### Behoben
- Crypto.com: `get_ticker()` rief falschen Endpunkt auf (`get-ticker` statt `get-tickers`)
- `mcp`-Paket auf `<2` gepinnt (v2.0 entfernte `FastMCP`)
- `CORE_FEATURE_SET` enthielt `macd_diff` (absolutes Preisniveau) statt einer skaleninvarianten Variante

## [0.2.0] - 2026-07-31

### Hinzugefügt
- Initiale Version als `trading-mcp-connector`: Crypto.com, TradingView, MetaTrader5
- 210 RL-Features, Regime-/Trenderkennung
- Binance- und Bybit-Anbindung
