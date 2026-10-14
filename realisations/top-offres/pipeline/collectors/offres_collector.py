import logging
from collections import Counter

from google.cloud import bigquery

from pipeline import config

logger = logging.getLogger(__name__)

TABLE_OFFRES = f"{config.GCP_PROJECT_ID}.{config.BQ_DATASET}.int_offres_a_scorer"


def lire_offres_a_scorer() -> list[dict]:
    """Offres à scorer (représentants sans filtre dur, non déjà scorées) du dernier build dbt."""
    requete = f"""
        SELECT id_unique, titre, entreprise_nom, entreprise_normalise, localisation_libelle, departement,
               type_contrat, type_contrat_libelle, salaire_libelle
        FROM `{TABLE_OFFRES}`
        WHERE a_scorer
        ORDER BY date_collecte DESC, id_unique
    """
    client = bigquery.Client(project=config.GCP_PROJECT_ID, location=config.BQ_LOCATION)
    offres = []
    for ligne in client.query(requete).result():
        offre = dict(ligne.items())
        offre["contrat"] = " / ".join(filter(None, [offre["type_contrat"], offre["type_contrat_libelle"]]))
        offres.append(offre)
    logger.info("Offres à scorer lues : %d", len(offres))
    return offres


def regrouper_entreprises(offres: list[dict]) -> list[dict]:
    """Entreprises distinctes {nom_normalise, nom_source, departement}, de la plus fréquente à la moins fréquente."""
    compteur = Counter(o["entreprise_normalise"] for o in offres if o["entreprise_normalise"])
    noms: dict[str, Counter] = {}
    departements: dict[str, Counter] = {}
    for offre in offres:
        cle = offre["entreprise_normalise"]
        if not cle:
            continue
        noms.setdefault(cle, Counter())[offre["entreprise_nom"]] += 1
        if offre["departement"]:
            departements.setdefault(cle, Counter())[offre["departement"]] += 1
    return [
        {
            "nom_normalise": cle,
            "nom_source": noms[cle].most_common(1)[0][0],
            "departement": departements[cle].most_common(1)[0][0] if cle in departements else None,
        }
        for cle, _ in compteur.most_common()
    ]
