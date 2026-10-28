"""
Lecture BigQuery de la nouvelle organisation de la page Immobilier (dataset immobilier).
Même compte de service et mêmes outils (client, cache, sérialisation) que immobilier_bigquery.py :
l'import ci-dessous est la seule dépendance vers le service V1.
Tables construites par realisations/immobilier/pipeline/organisation (noms définis dans pipeline/organisation/config.py).
"""

import logging

from app.services.immobilier_bigquery import _avec_cache, _get_bq_client, _serialiser, _table
from app.services.immobilier_org_cubes import CUBE_LOYERS, CUBES, colonnes

logger = logging.getLogger(__name__)

TABLE_PARAMETRES = "org_parametres"
TABLE_SOURCES = "org_sources"
TABLE_QUALITE = "org_qualite"


def _lire_table(nom: str, colonnes: str) -> list[dict]:
    """Colonnes demandées d'une petite table du dataset (jamais SELECT *), en cache."""
    def charger():
        client = _get_bq_client()
        lignes = _serialiser(client.query(f"SELECT {colonnes} FROM {_table(nom)}").result())
        logger.info(f"[immobilier_org_bigquery] {len(lignes)} lignes {nom} lues")
        return lignes

    return _avec_cache(nom, charger)


def fetch_parametres() -> list[dict]:
    """Période paramétrée et période réellement couverte par les ventes (une ligne)."""
    return _lire_table(
        TABLE_PARAMETRES,
        "livraison, code_departement, date_debut, date_fin, premiere_vente, derniere_vente, date_maj",
    )


def fetch_sources() -> list[dict]:
    """Une fiche par source, avec période, volume et dates de chargement mesurés."""
    return _lire_table(
        TABLE_SOURCES,
        "source, editeur, version, publiee, utilisee_par, limites, couverture, periode_debut, periode_fin, "
        "nb_lignes, chargee_le, utilisee_depuis, statut, date_maj",
    )


def fetch_qualite() -> list[dict]:
    """Un indicateur par ligne (format long : partie, indicateur, valeur, unité, commentaire)."""
    return _lire_table(TABLE_QUALITE, "partie, indicateur, valeur, unite, commentaire, date_maj")


def fetch_cube(cube: str) -> list[dict]:
    """Cube du registre : une ligne par cellule, avec la liste triée des prix au m² pour les cubes de ventes
    (en cache, ne pas modifier)."""
    return _lire_table(CUBES[cube]["table"], colonnes(cube))


def fetch_loyers() -> list[dict]:
    """Cube des ventes avec loyers : une ligne par cellule (quartier), listes triées de prix et de rendements,
    loyers uniques par cellule (en cache, ne pas modifier)."""
    return _lire_table(CUBE_LOYERS["table"], CUBE_LOYERS["colonnes"])
