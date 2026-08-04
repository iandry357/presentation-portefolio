"""
Collecteur PDF — Décisions de la Commission des sanctions ACPR.
Découvre automatiquement les décisions publiées sur le Recueil des sanctions
(page unique, non paginée), résout le lien PDF réel, télécharge et extrait
le texte. Un cache local (data/acpr_processed.json, volume Docker persistant)
évite de retraiter les décisions déjà collectées à chaque run.
"""
import hashlib
import io
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

import requests
import trafilatura

from urllib.parse import urljoin

from pipeline.config import ACPR_CACHE_PATH, ACPR_RECUEIL_URL

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BanqueDeFranceCollector/1.0)"
}
ACPR_BASE_URL = "https://acpr.banque-france.fr"

MOIS_FR = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}

# Exclure les arrêts/ordonnances du Conseil d'État — on ne garde que les décisions ACPR elles-mêmes
EXCLUDE_TITLE_PATTERNS = ("arrêt", "arret", "ordonnance")


# ── Cache local ──────────────────────────────────────────────

def _load_cache() -> Dict:
    """Charge le cache des décisions ACPR déjà traitées."""
    if not ACPR_CACHE_PATH.exists():
        return {}
    try:
        with open(ACPR_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"⚠️  Cache ACPR illisible, réinitialisation: {e}")
        return {}


def _save_cache(cache: Dict) -> None:
    """Sauvegarde le cache des décisions ACPR déjà traitées."""
    ACPR_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ACPR_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ── Découverte des décisions ─────────────────────────────────

def _fetch_markdown(url: str) -> Optional[str]:
    """Récupère une page et l'extrait en markdown avec liens préservés."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        return trafilatura.extract(
            downloaded,
            include_links=True,
            include_comments=False,
            include_tables=False,
            output_format="markdown",
        )
    except Exception as e:
        logger.warning(f"⚠️  Trafilatura échoué pour {url}: {e}")
        return None


def _extract_decision_number(title: str) -> Optional[str]:
    """Extrait le numéro de décision (ex: 2024-02, 2013-03 bis) depuis le titre."""
    match = re.search(r"n°\s*(\d{4}-\d{2}(?:\s*bis)?)", title, re.IGNORECASE)
    if match:
        return match.group(1).replace(" ", "_").lower()
    return None


def _extract_date(title: str) -> str:
    """Extrait et normalise la date (ex: '13 mai 2026') depuis le titre."""
    match = re.search(r"(\d{1,2})(?:er)?\s+(\w+)\s+(\d{4})", title, re.IGNORECASE)
    if match:
        day, month_name, year = match.groups()
        month = MOIS_FR.get(month_name.lower())
        if month:
            try:
                return datetime(int(year), month, int(day)).strftime("%Y-%m-%d")
            except ValueError:
                pass
    return datetime.utcnow().strftime("%Y-%m-%d")


def _parse_index(markdown: str) -> List[Dict]:
    """
    Parse le contenu markdown de la page Recueil des sanctions.
    Extrait chaque entrée : titre, lien, motif (si présent en ligne suivante).
    """
    entries = []
    
    pattern = re.compile(
        r"^-\s*\[([^\]]+)\]\(([^)\s]+)\)\s*$\n[ \t]*(?:\(([^)]+)\)\s*$)?",
        re.MULTILINE,
    )
    for match in pattern.finditer(markdown):
        title, url, motif = match.groups()
        title_clean = title.strip()

        if any(p in title_clean.lower() for p in EXCLUDE_TITLE_PATTERNS):
            continue
        if not title_clean.lower().startswith(("décision", "decision")):
            continue

        entries.append({
            "title": title_clean,
            "url": urljoin(ACPR_BASE_URL, url.strip()),
            "motif": motif.strip() if motif else "",
        })

    return entries


def _resolve_pdf_url(url: str) -> Optional[str]:
    """
    Résout l'URL PDF réelle d'une décision.
    Si l'URL pointe déjà vers un PDF, la retourne telle quelle.
    Sinon, fetch le HTML brut de la page intermédiaire (Trafilatura élague
    ces pages trop courtes en .extract(), donc on cherche l'attribut href
    directement dans le HTML plutôt que dans le contenu extrait).
    """
    if url.lower().endswith(".pdf"):
        return url

    try:
        downloaded = trafilatura.fetch_url(url)
    except Exception as e:
        logger.warning(f"⚠️  Fetch échoué pour {url}: {e}")
        return None

    if not downloaded:
        return None

    match = re.search(r'href\s*=\s*"([^"]+\.pdf)"', downloaded, re.IGNORECASE)
    if match:
        return urljoin(ACPR_BASE_URL, match.group(1))

    logger.warning(f"⚠️  Aucun lien PDF trouvé sur la page intermédiaire: {url}")
    return None


# ── Téléchargement et extraction texte (pattern identique SG) ──

def _download_pdf(url: str) -> Optional[bytes]:
    """Télécharge un PDF depuis une URL publique."""
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT, headers=HEADERS)
        response.raise_for_status()
        return response.content
    except Exception as e:
        logger.error(f"❌ Téléchargement échoué pour {url}: {e}")
        return None


def _extract_with_pymupdf(pdf_bytes: bytes) -> Optional[str]:
    """Extrait le texte brut via PyMuPDF (fitz)."""
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        for page in doc:
            text = page.get_text("text")
            if text.strip():
                pages.append(text.strip())
        doc.close()
        full_text = "\n\n".join(pages)
        return full_text if len(full_text.strip()) > 50 else None
    except Exception as e:
        logger.warning(f"⚠️  PyMuPDF échoué: {e}")
        return None


def _extract_with_pdfplumber(pdf_bytes: bytes) -> Optional[str]:
    """Extrait le texte brut via pdfplumber (fallback)."""
    try:
        import pdfplumber
        pages = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text and text.strip():
                    pages.append(text.strip())
        full_text = "\n\n".join(pages)
        return full_text if len(full_text.strip()) > 50 else None
    except Exception as e:
        logger.warning(f"⚠️  pdfplumber échoué: {e}")
        return None


def _extract_text(pdf_bytes: bytes, name: str) -> Optional[str]:
    """Extrait le texte brut d'un PDF. PyMuPDF en premier, pdfplumber en fallback."""
    text = _extract_with_pymupdf(pdf_bytes)
    if text:
        logger.info(f"✅ [{name}] extraction PyMuPDF réussie")
        return text

    logger.info(f"🔄 [{name}] PyMuPDF vide — fallback pdfplumber")
    text = _extract_with_pdfplumber(pdf_bytes)
    if text:
        logger.info(f"✅ [{name}] extraction pdfplumber réussie")
        return text

    logger.error(f"❌ [{name}] extraction échouée (PyMuPDF + pdfplumber)")
    return None


# ── Orchestration collecteur ─────────────────────────────────

def collect() -> List[Dict]:
    """
    Découvre, télécharge et extrait le texte des décisions ACPR
    non encore traitées (cache local).

    Returns:
        Liste de documents au format unifié pipeline.
    """
    logger.info("🔍 [acpr] — découverte du Recueil des sanctions")

    index_markdown = _fetch_markdown(ACPR_RECUEIL_URL)
    if not index_markdown:
        logger.error("❌ [acpr] Impossible de récupérer le Recueil des sanctions")
        return []

    entries = _parse_index(index_markdown)
    logger.info(f"📊 [acpr] {len(entries)} décisions référencées sur le Recueil")

    cache = _load_cache()
    all_docs = []
    new_count = 0

    for entry in entries:
        decision_number = _extract_decision_number(entry["title"]) or hashlib.md5(
            entry["title"].encode()
        ).hexdigest()[:12]

        if decision_number in cache:
            continue

        pdf_url = _resolve_pdf_url(entry["url"])
        if not pdf_url:
            continue

        pdf_bytes = _download_pdf(pdf_url)
        if not pdf_bytes:
            continue

        text = _extract_text(pdf_bytes, decision_number)
        if not text:
            continue

        doc_id = f"banque_acpr_{decision_number}"
        doc = {
            "id": doc_id,
            "source": "acpr_decision",
            "date": _extract_date(entry["title"]),
            "title": entry["title"],
            "content": text,
            "metadata": {
                "url": pdf_url,
                "doc_type": "decision_sanction",
                "motif": entry["motif"],
                "decision_number": decision_number,
                "source_name": "ACPR",
            },
        }
        all_docs.append(doc)
        cache[decision_number] = {
            "pdf_url": pdf_url,
            "processed_at": datetime.utcnow().isoformat(),
        }
        new_count += 1

    _save_cache(cache)
    logger.info(
        f"✅ [acpr] — {new_count} nouvelles décisions traitées, "
        f"{len(entries) - new_count} déjà en cache"
    )
    return all_docs