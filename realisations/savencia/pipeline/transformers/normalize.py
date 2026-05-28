"""
Normalisation des documents vers le format unifié pipeline.
Nettoie et valide la structure avant validation et chargement.
"""
import logging
import re
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)

VALID_SOURCES = {"google_news"}

def _clean_text(text: str) -> str:
    """Nettoie un champ texte — espaces, retours à la ligne multiples."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _normalize_date(date_str: str) -> str:
    """Normalise une date vers ISO 8601 YYYY-MM-DD."""
    if not date_str:
        return datetime.utcnow().strftime("%Y-%m-%d")

    formats = [
        "%Y-%m-%d",
        "%Y-%m",
        "%Y/%m/%d",
        "%Y",
        "%d %b %Y",
        "%b %Y",
        "%Y-%b",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    logger.warning(f"⚠️ Date non parseable: '{date_str}' — fallback today")
    return datetime.utcnow().strftime("%Y-%m-%d")


def normalize(doc: Dict) -> Dict:
    """
    Normalise un document vers le format unifié.

    Format attendu en sortie:
    {
        "id": str,
        "source": str,
        "date": str (YYYY-MM-DD),
        "title": str,
        "content": str,
        "metadata": dict
    }
    """
    return {
        "id": doc.get("id", "").strip(),
        "source": doc.get("source", "").strip().lower(),
        "date": _normalize_date(doc.get("date", "")),
        "title": _clean_text(doc.get("title", "")),
        "content": _clean_text(doc.get("content", "")),
        "metadata": doc.get("metadata", {}),
    }


def normalize_batch(docs: List[Dict]) -> List[Dict]:
    """
    Normalise une liste de documents.
    Filtre les documents avec source inconnue.
    """
    normalized = []
    skipped = 0

    for doc in docs:
        n = normalize(doc)
        if n["source"] not in VALID_SOURCES:
            logger.warning(f"⚠️ Source inconnue ignorée: '{n['source']}' — id: {n['id']}")
            skipped += 1
            continue
        normalized.append(n)

    logger.info(f"✅ Normalize — {len(normalized)} docs normalisés, {skipped} ignorés")
    return normalized