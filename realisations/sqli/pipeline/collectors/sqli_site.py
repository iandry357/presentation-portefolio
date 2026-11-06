"""
Collecteur site SQLI — pages de liste (première page seulement) + pages fixes.
robots.txt interdit /*?page=* : la pagination n'est jamais lue.
"""
import hashlib
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
import trafilatura
from lxml import html as lxml_html

from pipeline.config import (
    SITE_BASE_URL,
    SITE_GROUPS,
    SITE_PAGES,
    SITE_REQUEST_DELAY,
    SITE_USER_AGENT,
    TRAFILATURA_TIMEOUT,
)

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": SITE_USER_AGENT}
SITE_HOST = urlparse(SITE_BASE_URL).netloc


def _fetch_html(url: str) -> Optional[bytes]:
    """Télécharge une page HTML (octets bruts, l'encodage est détecté en aval)."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TRAFILATURA_TIMEOUT)
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        logger.warning(f"⚠️  Téléchargement impossible {url}: {e}")
        return None


def _extract_links(list_html: bytes, prefixes: List[str], max_pages: int) -> List[str]:
    """
    Liens d'articles d'une page de liste, dans l'ordre de la page, sans doublon.
    Les paramètres d'URL (?page=...) sont supprimés.
    """
    tree = lxml_html.fromstring(list_html)
    links: List[str] = []
    for href in tree.xpath("//a/@href"):
        parsed = urlparse(urljoin(SITE_BASE_URL, href))
        if parsed.netloc != SITE_HOST:
            continue
        path = parsed.path.rstrip("/")
        if not any(path.startswith(p) and len(path) > len(p) for p in prefixes):
            continue
        url = f"{SITE_BASE_URL}{path}"
        if url not in links:
            links.append(url)
        if len(links) >= max_pages:
            break
    return links


def _build_doc(url: str, page_html: bytes, group_name: str, dated: bool) -> Optional[Dict]:
    """
    Construit un document au format unifié pipeline.
    Date : lue sur la page si le groupe est daté, sinon date de collecte.
    """
    content = trafilatura.extract(page_html, include_comments=False, include_tables=False)
    meta = trafilatura.extract_metadata(page_html)
    title = (meta.title or "").strip() if meta else ""

    if not title or not content or len(content.strip()) < 50:
        logger.warning(f"⚠️  Page ignorée (titre ou contenu manquant): {url}")
        return None

    page_date = meta.date if (dated and meta and meta.date) else None

    return {
        "id": f"sqli_site_{hashlib.md5(url.encode()).hexdigest()[:16]}",
        "source": "sqli_site",
        "date": page_date or datetime.utcnow().strftime("%Y-%m-%d"),
        "title": title,
        "content": content,
        "metadata": {
            "url": url,
            "source_name": "sqli.com",
            "feed_name": group_name,
            "date_type": "publication" if page_date else "collecte",
        },
    }


def collect() -> List[Dict]:
    """
    Collecte les pages du site SQLI : articles des pages de liste (SITE_GROUPS)
    puis pages fixes (SITE_PAGES).

    Returns:
        Liste de documents au format unifié pipeline.
    """
    targets = []  # (url, nom du groupe, daté ou non)

    for group in SITE_GROUPS:
        list_url = urljoin(SITE_BASE_URL, group["list_url"])
        list_html = _fetch_html(list_url)
        time.sleep(SITE_REQUEST_DELAY)
        if not list_html:
            continue
        try:
            links = _extract_links(list_html, group["link_prefixes"], group["max_pages"])
        except Exception as e:
            logger.error(f"❌ [{group['name']}] liste illisible {list_url}: {e}")
            continue
        logger.info(f"🔍 [{group['name']}] — {len(links)} liens trouvés sur {list_url}")
        targets.extend((url, group["name"], group.get("dated", False)) for url in links)

    for page in SITE_PAGES:
        targets.append((urljoin(SITE_BASE_URL, page["url"]), page["name"], page.get("dated", False)))

    docs: List[Dict] = []
    seen_urls = set()
    for url, group_name, dated in targets:
        if url in seen_urls:
            continue
        seen_urls.add(url)

        page_html = _fetch_html(url)
        time.sleep(SITE_REQUEST_DELAY)
        if not page_html:
            continue

        doc = _build_doc(url, page_html, group_name, dated)
        if doc:
            docs.append(doc)

    logger.info(f"✅ Site SQLI total — {len(docs)} pages collectées")
    return docs
