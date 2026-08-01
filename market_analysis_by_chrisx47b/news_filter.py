"""
News-Filter-Modul.

WARUM RSS UND NICHT EINE NEWS-API: CryptoCompare (die naheliegende
keyless Crypto-News-API) verlangt inzwischen einen API-Key -- passt nicht
zur "kein Key noetig"-Linie der anderen Module. Offizielle RSS-Feeds
grosser Nachrichtenseiten (CoinDesk, Cointelegraph) sind weiterhin oeffentlich
und ohne Key abrufbar, deshalb die Basis hier.

WICHTIG (ehrlich, nicht getestet): Der XML-Parser unten folgt dem
Standard-RSS-2.0-Format (title/link/pubDate/description je <item>). Ich
konnte den echten Feed-Inhalt in dieser Sandbox nicht als Text abrufen
(Netzwerk-Domain nicht freigegeben, web_fetch lieferte Binaerdaten) -- die
Existenz und URL der Feeds ist mehrfach extern bestaetigt, der Parser selbst
ist ungetestet. Bitte lokal mit echten Daten verifizieren (siehe README).

Das Modul ist bewusst QUELLENUNABHAENGIG: filter_news()/score_relevance()/
classify_impact()/simple_sentiment() arbeiten auf einer Liste von dicts
(title, link, published, summary) -- egal ob die aus RSS, einer bezahlten
News-API oder einem anderen MCP-Connector (z.B. FMP:news) kommen.
"""

from __future__ import annotations
import re
import difflib
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

from .cache import ttl_cache

DEFAULT_FEEDS = {
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "cointelegraph": "https://cointelegraph.com/rss",
}

# Grobe, austauschbare Lexika -- kein ML-Sentiment, nur Keyword-Heuristik.
# Bewusst konservativ gehalten; false positives/negatives sind zu erwarten.
HIGH_IMPACT_KEYWORDS = [
    "sec", "etf", "ban", "hack", "hacked", "exploit", "lawsuit", "regulation",
    "regulatory", "fomc", "cpi", "interest rate", "rate decision", "bankruptcy",
    "delisting", "halt", "congress", "treasury", "sanction", "investigation",
]
POSITIVE_KEYWORDS = [
    "surge", "rally", "soar", "bullish", "gain", "approve", "approval",
    "partnership", "adoption", "upgrade", "record high", "breakout", "inflow",
]
NEGATIVE_KEYWORDS = [
    "crash", "plunge", "hack", "ban", "bearish", "lawsuit", "exploit",
    "selloff", "sell-off", "decline", "delist", "outflow", "liquidation",
]


@ttl_cache(seconds=300)
def fetch_rss(url: str) -> list[dict]:
    """Holt und parst einen RSS-2.0-Feed. Gibt eine Liste von dicts
    (title, link, published: datetime|None, summary) zurueck.
    Wirft KEINE Exception bei einzelnen defekten <item>s -- die werden
    uebersprungen, damit ein einzelner kaputter Eintrag nicht den ganzen Feed blockiert.
    """
    resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    items = []
    for item in root.findall(".//item"):
        try:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            summary = (item.findtext("description") or "").strip()
            pub_raw = item.findtext("pubDate")
            published = None
            if pub_raw:
                try:
                    published = parsedate_to_datetime(pub_raw)
                    if published.tzinfo is None:
                        published = published.replace(tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    published = None
            items.append({"title": title, "link": link, "summary": summary, "published": published})
        except Exception:
            continue
    return items


def fetch_all_feeds(feeds: dict[str, str] | None = None) -> list[dict]:
    """Holt mehrere Feeds und markiert jeden Eintrag mit seiner Quelle."""
    feeds = feeds or DEFAULT_FEEDS
    all_items = []
    for source_name, url in feeds.items():
        try:
            for item in fetch_rss(url):
                item["source"] = source_name
                all_items.append(item)
        except requests.RequestException as e:
            all_items.append({"title": None, "source": source_name, "error": str(e)})
    return all_items


def _text_of(item: dict) -> str:
    return f"{item.get('title', '')} {item.get('summary', '')}".lower()


def score_relevance(item: dict, keywords: list[str]) -> float:
    """Anteil der gesuchten Keywords, die in Titel/Summary vorkommen (0.0-1.0)."""
    if not keywords:
        return 1.0
    text = _text_of(item)
    hits = sum(1 for kw in keywords if kw.lower() in text)
    return round(hits / len(keywords), 3) if keywords else 0.0


def classify_impact(item: dict) -> str:
    """'high' bei Treffer auf HIGH_IMPACT_KEYWORDS, sonst 'normal'.
    Bewusst nur zwei Stufen -- eine feinere Skala wuerde false-precision suggerieren.
    """
    text = _text_of(item)
    return "high" if any(kw in text for kw in HIGH_IMPACT_KEYWORDS) else "normal"


def simple_sentiment(item: dict) -> dict:
    """Heuristisches Keyword-Sentiment. KEIN ML-Modell -- zaehlt nur Treffer
    aus POSITIVE_KEYWORDS/NEGATIVE_KEYWORDS. Fuer verlaessliche Einschaetzungen
    braucht es mehr als das; hier als grober erster Filter gedacht.
    """
    text = _text_of(item)
    pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in text)
    neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text)
    if pos > neg:
        label = "positive"
    elif neg > pos:
        label = "negative"
    else:
        label = "neutral"
    return {"label": label, "positive_hits": pos, "negative_hits": neg}


def deduplicate(items: list[dict], title_similarity_threshold: float = 0.85) -> list[dict]:
    """Entfernt Eintraege mit sehr aehnlichem Titel (mehrere Quellen berichten
    oft dieselbe Meldung fast wortgleich). Behaelt jeweils den ersten Treffer.
    """
    kept: list[dict] = []
    for item in items:
        title = (item.get("title") or "").lower().strip()
        if not title:
            continue
        is_dup = any(
            difflib.SequenceMatcher(None, title, (k.get("title") or "").lower().strip()).ratio()
            > title_similarity_threshold
            for k in kept
        )
        if not is_dup:
            kept.append(item)
    return kept


def filter_news(items: list[dict], keywords: list[str] | None = None,
                 exclude_keywords: list[str] | None = None,
                 hours: float | None = 48, min_relevance: float = 0.0) -> list[dict]:
    """Kombinierter Filter: Zeitfenster, Keyword-Relevanz, Ausschluss-Keywords,
    Deduplizierung, plus Impact-/Sentiment-Anreicherung je Eintrag.
    """
    now = datetime.now(timezone.utc)
    filtered = []
    for item in items:
        if item.get("error"):
            continue
        if hours is not None and item.get("published"):
            if now - item["published"] > timedelta(hours=hours):
                continue
        if exclude_keywords:
            text = _text_of(item)
            if any(kw.lower() in text for kw in exclude_keywords):
                continue
        relevance = score_relevance(item, keywords or [])
        if relevance < min_relevance:
            continue
        enriched = dict(item)
        enriched["relevance"] = relevance
        enriched["impact"] = classify_impact(item)
        enriched["sentiment"] = simple_sentiment(item)
        filtered.append(enriched)

    filtered = deduplicate(filtered)
    filtered.sort(key=lambda x: x.get("published") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return filtered


def get_filtered_news(keywords: list[str] | None = None, feeds: dict[str, str] | None = None,
                       hours: float = 48, min_relevance: float = 0.0,
                       only_high_impact: bool = False) -> list[dict]:
    """High-Level-Einstieg: holt alle Feeds, filtert, reichert an."""
    raw = fetch_all_feeds(feeds)
    result = filter_news(raw, keywords=keywords, hours=hours, min_relevance=min_relevance)
    if only_high_impact:
        result = [r for r in result if r["impact"] == "high"]
    return result
