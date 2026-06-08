"""
Validation qualité des documents normalisés.
Filtre les documents incomplets ou non conformes avant chargement.
"""
import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

# Seuils qualité
MIN_CONTENT_LENGTH = 50
MIN_TITLE_LENGTH = 5


def validate(doc: Dict) -> Tuple[bool, str]:
    """
    Valide un document normalisé.

    Returns:
        (is_valid, reason) — reason vide si valide
    """
    if not doc.get("id"):
        return False, "id manquant"

    if not doc.get("source"):
        return False, "source manquante"

    if not doc.get("title") or len(doc["title"]) < MIN_TITLE_LENGTH:
        return False, f"titre trop court (< {MIN_TITLE_LENGTH} chars)"

    if not doc.get("content") or len(doc["content"]) < MIN_CONTENT_LENGTH:
        return False, f"contenu trop court (< {MIN_CONTENT_LENGTH} chars)"

    if not doc.get("date"):
        return False, "date manquante"

    if not isinstance(doc.get("metadata"), dict):
        return False, "metadata invalide (doit être un dict)"

    return True, ""


def validate_batch(docs: List[Dict]) -> List[Dict]:
    """
    Valide une liste de documents.
    Retourne uniquement les documents valides.
    Logue les documents rejetés avec leur raison.
    """
    valid = []
    rejected = 0

    for doc in docs:
        is_valid, reason = validate(doc)
        if is_valid:
            valid.append(doc)
        else:
            logger.warning(f"⚠️ Document rejeté [{doc.get('id', 'unknown')}]: {reason}")
            rejected += 1

    logger.info(f"✅ Validation — {len(valid)} valides, {rejected} rejetés")
    return valid