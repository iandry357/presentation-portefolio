"""
Collecteur Google News RSS.
Récupère les actualités Sanofi IA/Data via feedparser.
"""
import logging
import feedparser
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import List, Dict

from typing import Optional
import trafilatura

from pipeline.config import (
    GOOGLE_NEWS_RSS_URL,
    GOOGLE_NEWS_MAX_RESULTS,
)

logger = logging.getLogger(__name__)


def _parse_date(entry: Dict) -> str:
    """Extrait et normalise la date d'une entrée RSS."""
    try:
        if hasattr(entry, "published"):
            dt = parsedate_to_datetime(entry.published)
            return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    return datetime.utcnow().strftime("%Y-%m-%d")


def _build_content(entry) -> str:
    """Construit un contenu enrichi depuis une entrée RSS."""
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
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        content = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
        return content if content and len(content.strip()) > 50 else None
    except Exception as e:
        logger.warning(f"⚠️  Trafilatura failed for {url}: {e}")
        return None


def collect(max_results: int = GOOGLE_NEWS_MAX_RESULTS) -> List[Dict]:
    """
    Collecte les actualités Sanofi depuis Google News RSS.

    Returns:
        Liste de documents au format unifié pipeline.
    """
    logger.info(f"🔍 Google News — collecte RSS (max {max_results})")

    try:
        feed = feedparser.parse(GOOGLE_NEWS_RSS_URL)
    except Exception as e:
        logger.error(f"❌ Google News RSS error: {e}")
        return []

    if feed.bozo and not feed.entries:
        logger.error(f"❌ Google News RSS invalide: {feed.bozo_exception}")
        return []

    docs = []
    for entry in feed.entries[:max_results]:
        entry_id = entry.get("id", entry.get("link", ""))
        if not entry_id:
            continue

        # Identifiant stable basé sur l'URL
        # doc_id = f"google_news_{abs(hash(entry_id))}"
        title = entry.get("title", "")
        # doc_id = f"google_news_{abs(hash(title))}"
        import hashlib
        doc_id = f"google_news_{hashlib.md5(title.encode()).hexdigest()[:16]}"

        article_url = entry.get("source", {}).get("href", "")

        doc = {
            "id": doc_id,
            "source": "google_news",
            "date": _parse_date(entry),
            "title": entry.get("title", ""),
            # "content": _build_content(entry),
            # "content": _fetch_content(entry.get("link", "")) or _build_content(entry),
            "content": _fetch_content(article_url) or _build_content(entry),
            "metadata": {
                # "url": entry.get("link", ""),
                "url": article_url or entry.get("link", ""),
                "source_name": entry.get("source", {}).get("title", ""),
                "rss_id": entry_id,
            },
        }
        docs.append(doc)

    logger.info(f"✅ Google News — {len(docs)} articles collectés")
    return docs