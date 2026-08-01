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

PERSISTENZ: Beide Historien wurden bisher rein im Prozessspeicher gehalten --
ein Neustart des Servers hat alles geloescht, es gab keine verlaessliche
Uptime-Aussage ueber Tage/Wochen. Jetzt wird jeder Eintrag zusaetzlich als
JSON-Zeile in eine lokale Datei angehaengt (Pfad konfigurierbar via
MARKET_ANALYSIS_HISTORY_FILE) und beim Start wieder eingelesen. Bewusst
simpel (append-only JSONL, kein DB-Treiber) -- reicht fuer die Grössenordnung
eines Einzelnutzer-Connectors. Ab 2 MB Dateigroesse wird beim naechsten
Schreibvorgang automatisch auf die letzten 1000 Zeilen gekuerzt.
"""

from __future__ import annotations
import os
import json
import time
import threading
from collections import deque
from datetime import datetime, timezone

import requests

ALERT_WEBHOOK_URL = os.environ.get("ALERT_WEBHOOK_URL", "").strip()
MAX_LOG_SIZE = 200
HISTORY_FILE = os.environ.get(
    "MARKET_ANALYSIS_HISTORY_FILE",
    os.path.join(os.getcwd(), "market_analysis_history.jsonl"),
)
_MAX_FILE_BYTES = 2 * 1024 * 1024
_TRIM_TO_LINES = 1000
_file_lock = threading.Lock()


def _append_to_history_file(record: dict) -> None:
    """Haengt einen Eintrag an die Historie-Datei an. Schreibfehler duerfen
    den eigentlichen Aufruf nie zum Absturz bringen -- nur best-effort."""
    try:
        with _file_lock:
            if os.path.exists(HISTORY_FILE) and os.path.getsize(HISTORY_FILE) > _MAX_FILE_BYTES:
                _trim_history_file()
            with open(HISTORY_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
    except OSError:
        pass  # Persistenz ist best-effort, kein kritischer Pfad


def _trim_history_file() -> None:
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines[-_TRIM_TO_LINES:])
    except OSError:
        pass


def _read_history_file(record_type: str) -> list[dict]:
    """Liest alle Zeilen mit passendem 'type'-Feld. Kaputte/fremde Zeilen
    werden stillschweigend uebersprungen (z.B. bei manueller Bearbeitung)."""
    if not os.path.exists(HISTORY_FILE):
        return []
    records = []
    try:
        with _file_lock, open(HISTORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("type") == record_type:
                    records.append(record)
    except OSError:
        return []
    return records


class AlertManager:
    def __init__(self, max_log_size: int = MAX_LOG_SIZE):
        self._log: deque = deque(maxlen=max_log_size)
        self._lock = threading.Lock()
        # Beim Start bereits vorhandene Alerts aus der Datei nachladen,
        # damit die Historie einen Neustart ueberlebt.
        for record in _read_history_file("alert")[-max_log_size:]:
            self._log.append({k: v for k, v in record.items() if k != "type"})

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
        _append_to_history_file({**entry, "type": "alert"})

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
        # Beim Start vorhandene Health-Check-Historie je Quelle nachladen.
        for record in _read_history_file("health_check"):
            source_name = record.get("source")
            if not source_name:
                continue
            entry = {k: v for k, v in record.items() if k != "type"}
            self._history.setdefault(source_name, deque(maxlen=history_size)).append(entry)

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
        _append_to_history_file({**result, "type": "health_check"})
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
