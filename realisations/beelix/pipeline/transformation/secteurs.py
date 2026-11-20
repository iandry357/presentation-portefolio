"""
Classement des offres par secteur Beelix — à partir du code NAF de l'entreprise.
Règles, dans l'ordre : Beelix elle-même (concurrence), cabinet de recrutement (intermédiaire),
NAF absent (non classé), préfixe NAF le plus long de SECTEURS_NAF, sinon autre.
"""
import logging
from collections import Counter
from typing import Dict, List, Optional

from pipeline.config import (
    BEELIX_NOM_NORMALISE,
    SECTEUR_AUTRE,
    SECTEUR_INTERMEDIAIRE,
    SECTEUR_NON_CLASSE,
    SECTEURS_LIBELLES,
    SECTEURS_NAF,
)

logger = logging.getLogger(__name__)

# Préfixes du plus long au plus court : le premier qui correspond est le plus précis
PREFIXES = sorted(SECTEURS_NAF, key=len, reverse=True)


def _secteur_naf(naf_code: Optional[str]) -> str:
    """Secteur déduit du code NAF (format « 62.02A »)."""
    code = (naf_code or "").strip()
    if not code:
        return SECTEUR_NON_CLASSE
    for prefixe in PREFIXES:
        if code.startswith(prefixe):
            return SECTEURS_NAF[prefixe]
    return SECTEUR_AUTRE


def classer(offre: Dict) -> str:
    """Secteur Beelix d'une offre."""
    if offre.get("entreprise_normalise") == BEELIX_NOM_NORMALISE:
        return "concurrence"
    if offre.get("type_entreprise") == "cabinet_recrutement":
        return SECTEUR_INTERMEDIAIRE
    return _secteur_naf(offre.get("naf_code"))


def enrichir(offres: List[Dict]) -> List[Dict]:
    """
    Ajoute à chaque offre (en place) : secteur, secteur_libelle, est_beelix.

    Returns:
        La même liste, enrichie.
    """
    for offre in offres:
        secteur = classer(offre)
        offre["secteur"] = secteur
        offre["secteur_libelle"] = SECTEURS_LIBELLES[secteur]
        offre["est_beelix"] = offre.get("entreprise_normalise") == BEELIX_NOM_NORMALISE

    repartition = Counter(o["secteur"] for o in offres)
    for secteur, nb in repartition.most_common():
        logger.info(f"   [{secteur}] {nb} offres")
    logger.info(f"✅ Secteurs — {len(offres)} offres classées, dont {sum(o['est_beelix'] for o in offres)} Beelix")
    return offres
