"""
Normalisation des articles legifrance vers le format unifié pipeline.
Nettoie et structure les documents avant chunking et chargement.
"""
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

SOURCE = "legifrance"


def _clean_text(text: str) -> str:
    """Nettoie un champ texte — espaces, retours à la ligne multiples."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _normalize_date(date_str: Optional[str]) -> Optional[str]:
    """
    Normalise une date vers ISO 8601 YYYY-MM-DD.

    Retourne None si la date est absente ou non parseable — pas de fallback
    sur la date du jour : une date d'entrée en vigueur juridique n'a pas de
    substitut valable, contrairement à une date d'ingestion.
    """
    if not date_str:
        return None

    formats = [
        "%Y-%m-%d",
        "%Y-%m",
        "%Y/%m/%d",
        "%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    logger.warning(f"⚠️ Date non parseable: '{date_str}' — champ laissé à None")
    return None


def _build_title(article_id: str, numero: str) -> str:
    """Génère un titre lisible à partir de l'id et du numéro d'article."""
    article_id = (article_id or "").strip()
    numero = (numero or "").strip()
    if article_id and numero:
        return f"{article_id} — Article {numero}"
    return article_id or numero or ""


def _join_thematiques(thematiques) -> str:
    """Joint la liste des thématiques en une chaîne unique séparée par des virgules."""
    if not thematiques:
        return ""
    return ",".join(t.strip() for t in thematiques if t and t.strip())

def _first_thematique(thematiques) -> str:
    """Ne conserve que la première thématique de la liste — simplification volontaire."""
    if not thematiques:
        return ""
    return (thematiques[0] or "").strip()

def normalize(doc: Dict) -> Dict:
    """
    Normalise un article legifrance vers le format unifié.

    Format attendu en sortie:
    {
        "id": str,
        "source": str,
        "date": str (YYYY-MM-DD) | None,
        "title": str,
        "content": str,
        "metadata": dict
    }
    """
    article_id = doc.get("id", "").strip()
    numero = doc.get("numero", "").strip()

    return {
        "id": article_id,
        "source": SOURCE,
        "date": _normalize_date(doc.get("date_debut")),
        "title": _build_title(article_id, numero),
        "content": _clean_text(doc.get("texte", "")),
        "metadata": {
            "numero": numero,
            "etat": doc.get("etat", ""),
            "date_debut": doc.get("date_debut"),
            "date_fin": doc.get("date_fin"),
            "thematique": _first_thematique(doc.get("thematiques", [])),
            "url_source": doc.get("url_source", ""),
        },
    }


def normalize_batch(docs: List[Dict]) -> List[Dict]:
    """
    Normalise une liste d'articles legifrance.
    Ignore les documents sans id exploitable ou sans contenu.
    """
    normalized = []
    skipped = 0

    for doc in docs:
        n = normalize(doc)
        if not n["id"] or not n["content"]:
            logger.warning(
                f"⚠️ Document ignoré (id ou content manquant) — id brut: {doc.get('id', 'unknown')}"
            )
            skipped += 1
            continue
        normalized.append(n)

    logger.info(f"✅ Normalize — {len(normalized)} docs normalisés, {skipped} ignorés")
    return normalized