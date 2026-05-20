"""
Collecteur Press Releases Sanofi.
Récupère les press releases via RSS + fetch contenu réel via Trafilatura.
"""
import hashlib
import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional

import feedparser
import trafilatura

from pipeline.config import (
    PRESS_RELEASES_MAX_RESULTS,
    PRESS_RELEASES_RSS_URL,
)

logger = logging.getLogger(__name__)


def _parse_date(entry) -> str:
    try:
        if hasattr(entry, "published"):
            dt = parsedate_to_datetime(entry.published)
            return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    return datetime.utcnow().strftime("%Y-%m-%d")


def _fetch_content(url: str) -> Optional[str]:
    """Fetch et extrait le contenu textuel d'une URL via Trafilatura."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        content = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
        return content if content and len(content.strip()) > 50 else None
    except Exception as e:
        logger.warning(f"⚠️  Trafilatura fetch failed for {url}: {e}")
        return None


def collect(max_results: int = PRESS_RELEASES_MAX_RESULTS) -> List[Dict]:
    """
    Collecte les press releases Sanofi depuis RSS + fetch contenu Trafilatura.

    Returns:
        Liste de documents au format unifié pipeline.
    """
    logger.info(f"🔍 Press Releases — collecte RSS (max {max_results})")

    try:
        feed = feedparser.parse(PRESS_RELEASES_RSS_URL)
    except Exception as e:
        logger.error(f"❌ Press Releases RSS error: {e}")
        return []

    if feed.bozo and not feed.entries:
        logger.error(f"❌ Press Releases RSS invalide: {feed.bozo_exception}")
        return []

    docs = []
    fetched, skipped = 0, 0

    for entry in feed.entries[:max_results]:
        title = entry.get("title", "")
        url = entry.get("link", "")
        if not title or not url:
            continue

        doc_id = f"press_release_{hashlib.md5(title.encode()).hexdigest()[:16]}"

        content = _fetch_content(url)
        if not content:
            logger.warning(f"⚠️  Contenu vide — skipped: {title[:60]}")
            skipped += 1
            continue

        doc = {
            "id": doc_id,
            "source": "press_releases",
            "date": _parse_date(entry),
            "title": title,
            "content": content,
            "metadata": {
                "url": url,
                "source_name": "Sanofi Press Releases",
                "rss_id": entry.get("id", url),
            },
        }
        docs.append(doc)
        fetched += 1

    logger.info(f"✅ Press Releases — {fetched} articles collectés, {skipped} skipped (contenu vide)")
    return docs