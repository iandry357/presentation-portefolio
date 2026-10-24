"""
Lecture BigQuery de l'onglet « Bâtiments (BDNB) » du MVP Immobilier (dataset immobilier).
Même compte de service et mêmes outils (client, cache, sérialisation) que immobilier_bigquery.py :
l'import ci-dessous est la seule dépendance vers le service V1.
Tables construites par realisations/immobilier/pipeline/bdnb (noms définis dans pipeline/bdnb/config.py).
"""

import logging

from app.services.immobilier_bigquery import _avec_cache, _get_bq_client, _serialiser, _table

logger = logging.getLogger(__name__)

TABLE_STATS = "agg_bdnb_stats"
TABLE_PARC_PERIODE = "agg_bdnb_parc_periode"
TABLE_PARC_ENERGIE = "agg_bdnb_parc_energie"
TABLE_DEPERDITIONS = "agg_bdnb_deperditions"
TABLE_GEOCODAGE = "agg_bdnb_geocodage"
TABLE_SOURCES = "bdnb_sources"
TABLE_ENTONNOIR = "bdnb_entonnoir"
TABLE_ANALYSE_VENTES = "agg_analyse_ventes"
TABLE_ANALYSE_DPE = "agg_analyse_dpe"
TABLE_QUALITE = "dvf_etalab_qualite"


def _lire_table(nom: str, colonnes: str) -> list[dict]:
    """Colonnes demandées d'une petite table du dataset (jamais SELECT *), en cache."""
    def charger():
        client = _get_bq_client()
        lignes = _serialiser(client.query(f"SELECT {colonnes} FROM {_table(nom)}").result())
        logger.info(f"[immobilier_bdnb_bigquery] {len(lignes)} lignes {nom} lues")
        return lignes

    return _avec_cache(nom, charger)


def fetch_stats() -> list[dict]:
    """Compteurs du bandeau (une ligne)."""
    return _lire_table(TABLE_STATS, "nb_batiments, nb_dpe, nb_adresses, date_maj")


def fetch_parc_periode() -> list[dict]:
    return _lire_table(TABLE_PARC_PERIODE, "periode_construction, etiquette, nb_dpe")


def fetch_parc_energie() -> list[dict]:
    return _lire_table(TABLE_PARC_ENERGIE, "energie_chauffage, etiquette, nb_dpe")


def fetch_deperditions() -> list[dict]:
    return _lire_table(TABLE_DEPERDITIONS, "periode_construction, poste, nb_logements, part_moyenne")


def fetch_geocodage() -> list[dict]:
    return _lire_table(TABLE_GEOCODAGE, "fiabilite, appariement, nb_liens")


def fetch_sources() -> list[dict]:
    return _lire_table(TABLE_SOURCES, "source, millesime, couverture, date_maj")


def fetch_entonnoir() -> list[dict]:
    return _lire_table(TABLE_ENTONNOIR, "etape, libelle, nb_dpe")


def fetch_qualite() -> list[dict]:
    """Validation du rattachement des ventes aux bâtiments : une ligne par (livraison, département, méthode, confirmé)."""
    return _lire_table(
        TABLE_QUALITE,
        "livraison, code_departement, methode, retrouvees, ok, erreur",
    )


def fetch_analyse_ventes() -> list[dict]:
    """Cube des ventes : une ligne par cellule, avec la liste triée des prix au m² (en cache, ne pas modifier)."""
    return _lire_table(
        TABLE_ANALYSE_VENTES,
        "trimestre, arrondissement, pieces, tranche_surface, etiquette, rattachee, nb_ventes, prix_m2, date_maj",
    )


def fetch_analyse_dpe() -> list[dict]:
    """Cube des DPE : une ligne par cellule (en cache)."""
    return _lire_table(
        TABLE_ANALYSE_DPE,
        "trimestre, arrondissement, pieces, tranche_surface, etiquette, nb_dpe, date_maj",
    )
