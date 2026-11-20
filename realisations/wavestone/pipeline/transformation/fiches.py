"""
Fiches texte des offres — Wavestone.
Une fiche par offre Wavestone de la fenêtre, au format unifié pipeline, pour l'indexation ChromaDB
(Ask AI : postes ouverts, profils recherchés). Texte complet au-delà de LONGUEUR_MIN_DESCRIPTION, sinon extrait.
Le score Top Offres (adéquation au profil candidat, 0 à 100) est repris ; sa raison ne l'est pas.
"""
import hashlib
import logging
from typing import Dict, List, Optional

from pipeline.config import LONGUEUR_MIN_DESCRIPTION

logger = logging.getLogger(__name__)

SOURCE_FICHE = "offre"


def _ligne(libelle: str, valeur: Optional[str]) -> str:
    """« Libellé : valeur », ou chaîne vide si la valeur manque."""
    valeur = (str(valeur) if valeur is not None else "").strip()
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
    entreprise = offre.get("entreprise_nom") or "Wavestone"
    score = offre.get("score")

    lignes = [
        _ligne("Offre", offre.get("titre")),
        _ligne("Entreprise", entreprise),
        _ligne("Lieu", offre.get("localisation_libelle")),
        _ligne("Contrat", offre.get("type_contrat_libelle")),
        _ligne("Salaire", offre.get("salaire_libelle")),
        _ligne("Publiée le", date),
        _ligne("Source", offre.get("source")),
        _ligne("Adéquation au profil du candidat (sur 100)", score),
        _ligne("Métier cible le plus proche", offre.get("cible_intitule") or offre.get("cible_proche")),
        _texte_description(offre.get("description")),
    ]

    return {
        "id": f"wavestone_offre_{hashlib.md5(offre['id_unique'].encode()).hexdigest()[:16]}",
        "source": SOURCE_FICHE,
        "date": date,
        "title": f"{offre.get('titre') or 'Offre'} — {entreprise}",
        "content": "\n".join(l for l in lignes if l),
        "metadata": {
            "url": offre.get("url_offre") or "",
            "id_unique": offre["id_unique"],
            "entreprise": entreprise,
            "score": score,
            "liste": offre.get("liste") or "",
            "source_offre": offre.get("source") or "",
            "date_type": "publication" if offre.get("date_publication") else "collecte",
        },
    }


def construire_fiches(offres: List[Dict]) -> List[Dict]:
    """
    Fiches de toutes les offres Wavestone de la fenêtre.

    Returns:
        Liste de documents au format unifié pipeline.
    """
    fiches = [construire(o) for o in offres]
    completes = sum(1 for f in fiches if "Description : " in f["content"])
    logger.info(f"✅ Fiches — {len(fiches)} fiches, dont {completes} avec texte complet")
    return fiches
