 
"""
rome_service.py
Déduction du code ROME et libellé depuis un intitulé de poste
via l'API ROMEO v2 de France Travail.
"""

import logging
from typing import Optional
from app.services.france_travail_client import predict_rome_codes

logger = logging.getLogger(__name__)

async def deduce_rome(title: str) -> tuple[Optional[str], Optional[str]]:
    """
    Appelle ROMEO v2 avec l'intitulé du poste et retourne
    le code ROME et son libellé les plus pertinents.

    Retourne (None, None) en cas d'échec — ne bloque jamais le pipeline.
    """
    try:
        # results = await predict_rome_codes(title)
        results = await predict_rome_codes(title, identifiant="job-rome")

        if not results:
            logger.warning(f"ROMEO v2 — aucun résultat pour : {title}")
            return None, None

        # On prend le premier résultat (score le plus élevé)
        top = results[0]
        rome_code = top.get("codeRome")
        rome_libelle = top.get("libelleRome")

        logger.info(f"ROMEO v2 — '{title}' → {rome_code} ({rome_libelle})")
        return rome_code, rome_libelle

    except Exception as e:
        logger.error(f"ROMEO v2 — erreur pour '{title}' : {e}")
        return None, None