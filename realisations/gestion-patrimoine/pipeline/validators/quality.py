"""
Validation qualité des chunks avant chargement BigQuery + ChromaDB.
Rejette silencieusement (avec log) tout chunk ne respectant pas les
garanties minimales attendues par le RAG en aval (citation d'article
obligatoire, filtrage par thématique).
"""
import logging
from typing import Dict, List

from pipeline.config import THEMATIQUES

logger = logging.getLogger(__name__)

VALID_THEMATIQUES = set(THEMATIQUES.keys())


def _is_valid(doc: Dict) -> bool:
    """Vérifie qu'un chunk respecte les garanties minimales."""
    if not doc.get("id", "").strip():
        return False

    if not doc.get("content", "").strip():
        return False

    numero = doc.get("metadata", {}).get("numero", "")
    if not numero or not numero.strip():
        return False

    thematique = doc.get("metadata", {}).get("thematique", "")
    if thematique not in VALID_THEMATIQUES:
        return False

    return True


def validate_batch(docs: List[Dict]) -> List[Dict]:
    """
    Filtre une liste de chunks, ne conservant que ceux respectant les
    garanties minimales (id, content, numero, thematique valide).
    """
    valid = []
    skipped = 0

    for doc in docs:
        if _is_valid(doc):
            valid.append(doc)
        else:
            logger.warning(f"⚠️ Chunk rejeté (validation qualité) — id: {doc.get('id', 'unknown')}")
            skipped += 1

    logger.info(f"✅ Validation — {len(valid)} chunks valides, {skipped} rejetés")
    return valid