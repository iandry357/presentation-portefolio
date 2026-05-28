"""
Collecteur Google News RSS — Savencia.
Collecte les actualités Savencia et agroalimentaire IA/Data via feedparser + Trafilatura.
"""
import hashlib
import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional

import feedparser
import trafilatura

from pipeline.config import (
    TRAFILATURA_MAX_RETRIES,
    TRAFILATURA_TIMEOUT,
    RSS_FEEDS,
)

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
    """Construit un contenu de fallback depuis les métadonnées RSS."""
    title = entry.get("title", "")
    summary = entry.get("summary", "")
    source = entry.get("source", {}).get("title", "")

    parts = [
        f"Titre: {title}",
        f"Source: {source}" if source else "",
        f"Résumé: {summary}" if summary else "",
    ]
    return "\n".join(p for p in parts if p)


def _fetch_content(url: str) -> Optional[str]:
    """Fetch et extrait le contenu textuel d'une URL via Trafilatura."""
    if not url:
        return None
    for attempt in range(TRAFILATURA_MAX_RETRIES):
        try:
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                continue
            content = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=False,
            )
            if content and len(content.strip()) > 50:
                return content
        except Exception as e:
            logger.warning(f"⚠️  Trafilatura attempt {attempt + 1} failed for {url}: {e}")
    return None


def _collect_feed(feed_cfg: Dict) -> List[Dict]:
    """
    Collecte les articles d'un flux RSS unique.

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
    for entry in feed.entries[:max_articles]:
        entry_id = entry.get("id", entry.get("link", ""))
        if not entry_id:
            continue

        title = entry.get("title", "")
        doc_id = f"savencia_{name}_{hashlib.md5(title.encode()).hexdigest()[:16]}"
        article_url = entry.get("source", {}).get("href", "")

        doc = {
            "id": doc_id,
            "source": "google_news",
            "date": _parse_date(entry),
            "title": title,
            "content": _fetch_content(article_url) or _build_content(entry),
            "metadata": {
                "url": article_url or entry.get("link", ""),
                "source_name": entry.get("source", {}).get("title", ""),
                "feed_name": name,
                "rss_id": entry_id,
            },
        }
        docs.append(doc)

    logger.info(f"✅ [{name}] — {len(docs)} articles collectés")
    return docs


def collect() -> List[Dict]:
    """
    Collecte les actualités depuis tous les flux RSS configurés.

    Returns:
        Liste consolidée de documents au format unifié pipeline.
    """
    all_docs = []
    for feed_cfg in RSS_FEEDS:
        docs = _collect_feed(feed_cfg)
        all_docs.extend(docs)

    logger.info(f"✅ Google News total — {len(all_docs)} articles collectés")
    return all_docs