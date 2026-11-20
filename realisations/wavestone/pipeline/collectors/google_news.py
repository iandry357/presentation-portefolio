"""
Collecteur Google News RSS — Wavestone (presse).
Les sources de RSS_SOURCES_EXCLUES (wavestone.com) sont écartées : collectées directement sur le site.
Contenu = titre, source et résumé du flux : la balise <source> ne donne que la racine du média,
et le lien Google News est encodé (pas d'accès direct à l'article).
"""
import hashlib
import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Dict, List

import feedparser

from pipeline.config import RSS_FEEDS, RSS_SOURCES_EXCLUES

logger = logging.getLogger(__name__)


def _parse_date(entry) -> str:
    """Extrait et normalise la date d'une entrée RSS."""
    try:
        if hasattr(entry, "published"):
            dt = parsedate_to_datetime(entry.published)
            return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    return datetime.utcnow().strftime("%Y-%m-%d")


def _build_content(entry) -> str:
    """Contenu depuis les métadonnées RSS (titre, source, résumé)."""
    title = entry.get("title", "")
    summary = entry.get("summary", "")
    source = entry.get("source", {}).get("title", "")

    parts = [
        f"Titre: {title}",
        f"Source: {source}" if source else "",
        f"Résumé: {summary}" if summary else "",
    ]
    return "\n".join(p for p in parts if p)


def _collect_feed(feed_cfg: Dict) -> List[Dict]:
    """
    Collecte les articles d'un flux RSS unique, hors sources exclues.

    Args:
        feed_cfg: entrée de RSS_FEEDS (name, url, max_articles)

    Returns:
        Liste de documents au format unifié pipeline.
    """
    name = feed_cfg["name"]
    url = feed_cfg["url"]
    max_articles = feed_cfg["max_articles"]

    logger.info(f"🔍 [{name}] — collecte RSS (max {max_articles})")

    try:
        feed = feedparser.parse(url)
    except Exception as e:
        logger.error(f"❌ [{name}] RSS parse error: {e}")
        return []

    if feed.bozo and not feed.entries:
        logger.error(f"❌ [{name}] RSS invalide: {feed.bozo_exception}")
        return []

    docs = []
    exclus = 0
    for entry in feed.entries[:max_articles]:
        entry_id = entry.get("id", entry.get("link", ""))
        if not entry_id:
            continue

        source_href = entry.get("source", {}).get("href", "").rstrip("/")
        if source_href in RSS_SOURCES_EXCLUES:
            exclus += 1
            continue

        title = entry.get("title", "")
        doc = {
            "id": f"wavestone_{name}_{hashlib.md5(title.encode()).hexdigest()[:16]}",
            "source": "google_news",
            "date": _parse_date(entry),
            "title": title,
            "content": _build_content(entry),
            "metadata": {
                "url": entry.get("link", "") or source_href,
                "source_name": entry.get("source", {}).get("title", ""),
                "feed_name": name,
                "langue": name.rsplit("_", 1)[-1],
                "rss_id": entry_id,
                "date_type": "publication",
            },
        }
        docs.append(doc)

    logger.info(f"✅ [{name}] — {len(docs)} articles collectés, {exclus} exclus (source du site)")
    return docs


def collect() -> List[Dict]:
    """
    Collecte la presse depuis tous les flux RSS configurés (dédoublonnage par titre).

    Returns:
        Liste consolidée de documents au format unifié pipeline.
    """
    all_docs = []
    seen_titles = set()
    for feed_cfg in RSS_FEEDS:
        for doc in _collect_feed(feed_cfg):
            if doc["title"] in seen_titles:
                continue
            seen_titles.add(doc["title"])
            all_docs.append(doc)

    logger.info(f"✅ Google News total — {len(all_docs)} articles collectés")
    return all_docs
