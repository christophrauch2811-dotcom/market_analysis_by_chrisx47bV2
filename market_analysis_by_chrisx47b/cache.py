"""
Einfacher In-Memory-TTL-Cache fuer API-Aufrufe.

Ziel: bei RL-Trainingslaeufen mit vielen Episoden nicht bei jedem Schritt
dieselben Kerzen erneut von Crypto.com/TradingView/MT5 abzufragen und nicht
in API-Rate-Limits zu laufen (Crypto.com: 100 req/s fuer public-Endpunkte).

Bewusst simpel gehalten (kein Redis/Disk-Cache) -- reicht fuer einen
Single-Process-Connector. Bei Bedarf leicht gegen einen persistenten
Cache (z.B. diskcache) austauschbar, da nur ttl_cache() ausgetauscht werden muesste.
"""

from __future__ import annotations
import time
import functools
import threading

import requests

_LOCK = threading.Lock()


def retry_with_backoff(max_attempts: int = 3, base_delay: float = 1.0,
                        retry_on: tuple = (requests.exceptions.RequestException,)):
    """Wiederholt einen fehlschlagenden API-Call mit exponentiellem Backoff
    (base_delay, base_delay*2, base_delay*4, ...). Faengt nur transiente
    Netzwerkfehler (Timeout, ConnectionError, 5xx via raise_for_status) --
    kein tenacity/httpx noetig, reine Standardbibliothek + requests, das
    schon Abhaengigkeit ist. Nach dem letzten Versuch wird die Exception
    unveraendert weitergereicht (kein Verschlucken echter Fehler).
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except retry_on as e:
                    last_exc = e
                    if attempt < max_attempts - 1:
                        time.sleep(base_delay * (2 ** attempt))
            raise last_exc
        return wrapper
    return decorator


def ttl_cache(seconds: float = 30.0, maxsize: int = 256):
    """Decorator: cached ein Funktionsergebnis fuer `seconds` Sekunden,
    schluesselt nach Funktionsargumenten. Threadsafe genug fuer den MCP-Server
    (ein Prozess, mehrere Requests).
    """
    def decorator(func):
        cache: dict = {}

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.monotonic()
            with _LOCK:
                if key in cache:
                    value, expires_at = cache[key]
                    if now < expires_at:
                        return value
                if len(cache) >= maxsize:
                    # Aeltesten Eintrag verwerfen (einfaches FIFO statt LRU -- reicht hier)
                    oldest_key = next(iter(cache))
                    cache.pop(oldest_key, None)

            result = func(*args, **kwargs)

            with _LOCK:
                cache[key] = (result, now + seconds)
            return result

        wrapper.cache_clear = lambda: cache.clear()
        return wrapper

    return decorator


class RateLimiter:
    """Einfacher Token-Bucket-Rate-Limiter, um Quellen-APIs nicht zu ueberlasten.
    Blockiert kurz (time.sleep), statt einen Fehler zu werfen -- fuer einen
    MCP-Tool-Call ist ein kurzes Warten unproblematischer als ein Abbruch.
    """

    def __init__(self, max_calls: int, per_seconds: float):
        self.max_calls = max_calls
        self.per_seconds = per_seconds
        self._calls: list[float] = []
        self._lock = threading.Lock()

    def acquire(self):
        with self._lock:
            now = time.monotonic()
            self._calls = [t for t in self._calls if now - t < self.per_seconds]
            if len(self._calls) >= self.max_calls:
                sleep_time = self.per_seconds - (now - self._calls[0])
                if sleep_time > 0:
                    time.sleep(sleep_time)
            self._calls.append(time.monotonic())


# Vorkonfigurierte Limiter je Quelle (konservativ, deutlich unter den
# offiziellen Limits, z.B. Crypto.com: 100 req/s fuer public-Endpunkte)
crypto_com_limiter = RateLimiter(max_calls=20, per_seconds=1.0)
tradingview_limiter = RateLimiter(max_calls=5, per_seconds=1.0)
