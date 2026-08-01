"""
Monitoring/Alerting fuer den Connector.

Zweck: merken, wenn eine Quelle ausfaellt, ungewoehnlich langsam antwortet
oder Daten liefert, die die Qualitaetspruefung nicht besteht -- statt das
erst indirekt am Trainingsergebnis zu merken.

Zwei Bausteine:
  1. HealthMonitor -- fuehrt Health-Checks je Quelle aus (Latenz, Erfolg/Fehler),
     haelt eine kurze Historie im Speicher.
  2. AlertManager -- sammelt Alerts (Level + Quelle + Nachricht), haelt ein
     begrenztes In-Memory-Log, und sendet optional an einen Webhook
     (Slack/Discord-kompatibles JSON), wenn ALERT_WEBHOOK_URL gesetzt ist.

Bewusst ohne externe Abhaengigkeiten (kein Slack-SDK etc.) -- ein simpler
POST-Request auf eine konfigurierbare Webhook-URL deckt Slack, Discord und
die meisten "Incoming Webhook"-Integrationen ab.
"""

from __future__ import annotations
import os
import time
import threading
from collections import deque
from datetime import datetime, timezone

import requests

ALERT_WEBHOOK_URL = os.environ.get("ALERT_WEBHOOK_URL", "").strip()
MAX_LOG_SIZE = 200


class AlertManager:
    def __init__(self, max_log_size: int = MAX_LOG_SIZE):
        self._log: deque = deque(maxlen=max_log_size)
        self._lock = threading.Lock()

    def send(self, level: str, source: str, message: str, extra: dict | None = None) -> dict:
        """level: 'info' | 'warning' | 'critical'"""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "source": source,
            "message": message,
            "extra": extra or {},
        }
        with self._lock:
            self._log.append(entry)

        if ALERT_WEBHOOK_URL and level in ("warning", "critical"):
            try:
                # Slack/Discord-kompatibles Minimalformat ("text"-Feld wird von beiden verstanden)
                requests.post(
                    ALERT_WEBHOOK_URL,
                    json={"text": f"[{level.upper()}] {source}: {message}"},
                    timeout=5,
                )
            except requests.RequestException as e:
                # Alerting darf den eigentlichen Aufruf nie zum Absturz bringen
                with self._lock:
                    self._log.append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "level": "warning", "source": "alert_manager",
                        "message": f"Webhook-Versand fehlgeschlagen: {e}", "extra": {},
                    })
        return entry

    def recent(self, limit: int = 20, level: str | None = None) -> list:
        with self._lock:
            items = list(self._log)
        if level:
            items = [i for i in items if i["level"] == level]
        return items[-limit:]


class HealthMonitor:
    """Fuehrt einen Health-Check (eine leichte API-Anfrage) je Quelle aus und
    merkt sich die letzten Ergebnisse. `check_fn` ist eine Funktion ohne
    Argumente, die bei Erfolg irgendetwas zurueckgibt und bei Fehler eine
    Exception wirft (z.B. lambda: crypto_com.get_ticker('BTC_USDT')).
    """

    def __init__(self, alert_manager: AlertManager, history_size: int = 50):
        self.alerts = alert_manager
        self._history: dict[str, deque] = {}
        self._lock = threading.Lock()
        self._history_size = history_size

    def check(self, source_name: str, check_fn) -> dict:
        start = time.monotonic()
        try:
            check_fn()
            latency_ms = round((time.monotonic() - start) * 1000, 1)
            result = {"source": source_name, "status": "ok", "latency_ms": latency_ms,
                      "timestamp": datetime.now(timezone.utc).isoformat()}
        except Exception as e:
            latency_ms = round((time.monotonic() - start) * 1000, 1)
            result = {"source": source_name, "status": "error", "latency_ms": latency_ms,
                      "error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}
            self.alerts.send("critical", source_name, f"Health-Check fehlgeschlagen: {e}")

        with self._lock:
            self._history.setdefault(source_name, deque(maxlen=self._history_size)).append(result)
        return result

    def uptime(self, source_name: str) -> float | None:
        with self._lock:
            hist = list(self._history.get(source_name, []))
        if not hist:
            return None
        ok_count = sum(1 for h in hist if h["status"] == "ok")
        return round(ok_count / len(hist), 3)

    def history(self, source_name: str, limit: int = 20) -> list:
        with self._lock:
            hist = list(self._history.get(source_name, []))
        return hist[-limit:]


# Ein gemeinsamer, prozessweiter Zustand -- reicht fuer einen Single-Process-MCP-Server.
alert_manager = AlertManager()
health_monitor = HealthMonitor(alert_manager)


def alert_on_data_quality(quality: dict, source: str, symbol: str) -> None:
    """Von rl_feature_vector/check_data_quality aufgerufen: meldet einen
    Alert, wenn validate_ohlcv() Probleme gefunden hat. Bricht nichts ab --
    die Berechnung laeuft weiter, der Alert ist nur ein Signal nach aussen.
    """
    if not quality.get("is_valid", True):
        alert_manager.send(
            "warning", source,
            f"Datenqualitaetsprobleme bei {symbol}: {'; '.join(quality.get('issues', []))}",
            extra={"symbol": symbol, "row_count": quality.get("row_count")},
        )
