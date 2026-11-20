"""
Collecteur site Wavestone — URL tirées des sous-sitemaps Yoast (FR et EN), extraction trafilatura.
robots.txt du 2026-11-20 : seuls /wp-json/ et /?rest_route= sont interdits (non utilisés ici).
Date : datePublished du JSON-LD Yoast (vérifié sur news, insight, clients-story), sinon date de collecte.
"""
import hashlib
import json
import logging
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

import requests
import trafilatura
from google.cloud import bigquery
from google.oauth2 import service_account
from lxml import etree

from pipeline.config import (
    BQ_DATASET,
    BQ_TABLE_NEWS,
    GCP_PROJECT_ID,
    GCP_SA_KEY_PATH,
    SITE_BASE_URL,
    SITE_FRAGMENTS_A_SUPPRIMER,
    SITE_INCREMENTAL,
    SITE_LANGUES,
    SITE_MARQUEURS_FIN,
    SITE_MAX_PAGES_PAR_SECTION,
    SITE_REQUEST_DELAY,
    SITE_SECTIONS,
    SITE_USER_AGENT,
    TRAFILATURA_TIMEOUT,
)

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": SITE_USER_AGENT}
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
SOURCE = "wavestone_site"
RE_DATE_PUBLIEE = re.compile(r'"datePublished":"(\d{4}-\d{2}-\d{2})')
RE_SUFFIXE_TITRE = re.compile(r"\s*[|–-]\s*Wavestone( Insights)?\s*$")


def _fetch(url: str) -> Tuple[Optional[bytes], Optional[int]]:
    """Télécharge une URL ; renvoie (octets ou None, code HTTP ou None si erreur réseau)."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TRAFILATURA_TIMEOUT)
        if resp.status_code != 200:
            return None, resp.status_code
        return resp.content, 200
    except Exception as e:
        logger.warning(f"⚠️  Téléchargement impossible {url}: {e}")
        return None, None


def _urls_sitemap(section: Dict) -> Dict[str, List[Tuple[str, str]]]:
    """
    URL d'une section par langue, triées de la plus récente à la plus ancienne (lastmod).
    Gardées : chemin /<langue>/<segment>/<slug>/ pour les langues de SITE_LANGUES.
    """
    contenu, code = _fetch(f"{SITE_BASE_URL}{section['sitemap']}")
    time.sleep(SITE_REQUEST_DELAY)
    par_langue: Dict[str, List[Tuple[str, str]]] = {lang: [] for lang in SITE_LANGUES}
    if not contenu:
        logger.error(f"❌ [{section['name']}] sitemap illisible (HTTP {code})")
        return par_langue

    racine = etree.fromstring(contenu)
    for noeud in racine.findall("sm:url", SITEMAP_NS):
        loc = (noeud.findtext("sm:loc", default="", namespaces=SITEMAP_NS) or "").strip()
        lastmod = (noeud.findtext("sm:lastmod", default="", namespaces=SITEMAP_NS) or "").strip()
        morceaux = [m for m in urlparse(loc).path.split("/") if m]
        if len(morceaux) < 3 or morceaux[0] not in SITE_LANGUES or morceaux[1] != section["segment"]:
            continue
        par_langue[morceaux[0]].append((loc, lastmod))

    for lang in par_langue:
        par_langue[lang].sort(key=lambda x: x[1], reverse=True)
        if SITE_MAX_PAGES_PAR_SECTION > 0:
            par_langue[lang] = par_langue[lang][:SITE_MAX_PAGES_PAR_SECTION]
    return par_langue


def _urls_existantes() -> Set[str]:
    """URL du site déjà présentes dans articles_bruts (vide si la table n'existe pas encore)."""
    credentials = service_account.Credentials.from_service_account_file(
        str(GCP_SA_KEY_PATH),
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    client = bigquery.Client(project=GCP_PROJECT_ID, credentials=credentials)
    table_ref = f"{GCP_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE_NEWS}"
    try:
        client.get_table(table_ref)
    except Exception:
        return set()
    query = f"""
        SELECT DISTINCT JSON_VALUE(metadata, '$.url') AS url
        FROM `{table_ref}`
        WHERE source = '{SOURCE}'
    """
    return {row.url for row in client.query(query).result() if row.url}


def _nettoyer(texte: str) -> str:
    """Coupe le texte au premier marqueur de fin trouvé, puis retire les fragments parasites."""
    positions = [texte.find(m) for m in SITE_MARQUEURS_FIN if m in texte]
    if positions:
        texte = texte[: min(positions)]
    for fragment in SITE_FRAGMENTS_A_SUPPRIMER:
        texte = texte.replace(fragment, " ")
    return texte.strip()


def _build_doc(url: str, page_html: bytes, section: str, langue: str, lastmod: str) -> Optional[Dict]:
    """Construit un document au format unifié pipeline."""
    contenu = trafilatura.extract(page_html, include_comments=False, include_tables=False)
    meta = trafilatura.extract_metadata(page_html)
    titre = RE_SUFFIXE_TITRE.sub("", (meta.title or "").strip()) if meta else ""
    contenu = _nettoyer(contenu or "")

    if not titre or len(contenu) < 50:
        logger.warning(f"⚠️  Page ignorée (titre ou contenu manquant): {url}")
        return None

    trouve = RE_DATE_PUBLIEE.search(page_html.decode("utf-8", errors="ignore"))
    date_publiee = trouve.group(1) if trouve else None

    return {
        "id": f"{SOURCE}_{hashlib.md5(url.encode()).hexdigest()[:16]}",
        "source": SOURCE,
        "date": date_publiee or datetime.utcnow().strftime("%Y-%m-%d"),
        "title": titre,
        "content": contenu,
        "metadata": {
            "url": url,
            "source_name": "wavestone.com",
            "feed_name": f"{section}_{langue}",
            "section": section,
            "langue": langue,
            "lastmod": lastmod,
            "date_type": "publication" if date_publiee else "collecte",
        },
    }


def collect() -> List[Dict]:
    """
    Collecte les pages du site Wavestone : pour chaque section et langue, URL du sous-sitemap,
    URL déjà en base sautées (SITE_INCREMENTAL), pages en erreur comptées sans arrêter le run.

    Returns:
        Liste de documents au format unifié pipeline.
    """
    existantes = _urls_existantes() if SITE_INCREMENTAL else set()
    logger.info(f"🔍 Site Wavestone — {len(existantes)} URL déjà en base")

    docs: List[Dict] = []
    for section in SITE_SECTIONS:
        for langue, urls in _urls_sitemap(section).items():
            stats = {"candidates": len(urls), "deja_en_base": 0, "erreurs_http": 0, "ignorees": 0, "collectees": 0}
            for url, lastmod in urls:
                if url in existantes:
                    stats["deja_en_base"] += 1
                    continue
                page_html, code = _fetch(url)
                time.sleep(SITE_REQUEST_DELAY)
                if not page_html:
                    stats["erreurs_http"] += 1
                    logger.warning(f"⚠️  HTTP {code} : {url}")
                    continue
                doc = _build_doc(url, page_html, section["name"], langue, lastmod)
                if doc:
                    docs.append(doc)
                    stats["collectees"] += 1
                else:
                    stats["ignorees"] += 1
            logger.info(f"📄 [{section['name']}/{langue}] {json.dumps(stats)}")

    logger.info(f"✅ Site Wavestone total — {len(docs)} pages collectées")
    return docs
