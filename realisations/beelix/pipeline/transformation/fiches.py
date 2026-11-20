"""
Fiches texte des offres — Beelix.
Une fiche par offre des secteurs RAG (secteurs Beelix + concurrence), au format unifié pipeline,
pour l'indexation ChromaDB. Texte complet repris au-delà de LONGUEUR_MIN_DESCRIPTION, sinon extrait.
"""
import hashlib
import logging
from typing import Dict, List, Optional

from pipeline.config import LONGUEUR_MIN_DESCRIPTION, SECTEURS_RAG

logger = logging.getLogger(__name__)

SOURCE_FICHE = "offre"


def _ligne(libelle: str, valeur: Optional[str]) -> str:
    """« Libellé : valeur », ou chaîne vide si la valeur manque."""
    valeur = (valeur or "").strip()
    return f"{libelle} : {valeur}" if valeur else ""


def _texte_description(description: Optional[str]) -> str:
    """Texte complet si assez long, sinon extrait signalé comme tel."""
    texte = (description or "").strip()
    if not texte:
        return ""
    if len(texte) >= LONGUEUR_MIN_DESCRIPTION:
        return f"Description : {texte}"
    return f"Extrait : {texte}"


def construire(offre: Dict) -> Dict:
    """Fiche d'une offre au format unifié pipeline."""
    date = (offre.get("date_publication") or offre.get("date_collecte") or "")[:10]
    entreprise = offre.get("entreprise_nom") or "Entreprise non précisée"
    secteur = offre["secteur_libelle"]
    if offre.get("naf_libelle"):
        secteur = f"{secteur} (NAF : {offre['naf_libelle']})"

    lignes = [
        _ligne("Offre", offre.get("titre")),
        _ligne("Entreprise", entreprise),
        _ligne("Secteur", secteur),
        _ligne("Lieu", offre.get("localisation_libelle")),
        _ligne("Contrat", offre.get("type_contrat_libelle")),
        _ligne("Salaire", offre.get("salaire_libelle")),
        _ligne("Publiée le", date),
        _ligne("Source", offre.get("source")),
        _texte_description(offre.get("description")),
    ]

    return {
        "id": f"beelix_offre_{hashlib.md5(offre['id_unique'].encode()).hexdigest()[:16]}",
        "source": SOURCE_FICHE,
        "date": date,
        "title": f"{offre.get('titre') or 'Offre'} — {entreprise}",
        "content": "\n".join(l for l in lignes if l),
        "metadata": {
            "url": offre.get("url_offre") or "",
            "id_unique": offre["id_unique"],
            "entreprise": entreprise,
            "secteur": offre["secteur"],
            "est_beelix": bool(offre.get("est_beelix")),
            "source_offre": offre.get("source") or "",
            "date_type": "publication" if offre.get("date_publication") else "collecte",
        },
    }


def construire_fiches(offres: List[Dict]) -> List[Dict]:
    """
    Fiches des offres des secteurs RAG.

    Returns:
        Liste de documents au format unifié pipeline.
    """
    fiches = [construire(o) for o in offres if o.get("secteur") in SECTEURS_RAG]
    completes = sum(1 for f in fiches if "Description : " in f["content"])
    logger.info(f"✅ Fiches — {len(fiches)} fiches (secteurs RAG), dont {completes} avec texte complet")
    return fiches
