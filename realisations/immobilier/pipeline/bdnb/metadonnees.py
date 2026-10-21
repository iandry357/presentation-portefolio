import logging

import polars as pl

from pipeline.bdnb.aggregations import _creer_table
from pipeline.bdnb.config import (
    ARRETE_2021, METHODE_DPE, SOURCES, SUFFIXE_TYPE_DPE, SURFACE_MIN, TABLE_ENTONNOIR, TABLE_SOURCES, TABLES,
)
from pipeline.bdnb.selection import lire

logger = logging.getLogger(__name__)


def _litteral(valeur):
    """Texte SQL : chaîne entre apostrophes (échappées), ou NULL."""
    return "NULL" if valeur is None else "'" + valeur.replace("'", "''") + "'"


def _entonnoir():
    """Nombre de DPE restant après chaque filtre de la sélection, compté sur le Parquet BDNB avant chargement."""
    base = lire("dpe_logement")
    arrete = base.filter(pl.col("arrete_2021") == ARRETE_2021)
    logement = arrete.filter(pl.col("type_dpe").str.ends_with(SUFFIXE_TYPE_DPE))
    methode = logement.filter(pl.col("type_dpe").str.contains(METHODE_DPE, literal=True))
    surface = methode.filter(pl.col("surface_habitable_logement") > SURFACE_MIN)
    etapes = [
        ("DPE de la BDNB (Paris)", base),
        ("Arrêté 2021", arrete),
        ("Logement (hors immeuble)", logement),
        (f"Méthode {METHODE_DPE}", methode),
        ("Surface habitable > 0", surface),
    ]
    resultat = [(i, libelle, lf.select(pl.len()).collect().item()) for i, (libelle, lf) in enumerate(etapes, start=1)]

    attendu = TABLES["bdnb_dpe_logement"]["lignes"]
    if resultat[-1][2] != attendu:
        raise ValueError(f"Entonnoir : {resultat[-1][2]} DPE à la dernière étape, {attendu} attendus")
    return resultat


def construire_metadonnees():
    """Crée bdnb_sources (millésimes) et bdnb_entonnoir (étapes de la sélection DPE)."""
    sources = ", ".join(
        f"STRUCT({_litteral(s['source'])} AS source, {_litteral(s['millesime'])} AS millesime, "
        f"{_litteral(s['couverture'])} AS couverture)"
        for s in SOURCES
    )
    _creer_table(TABLE_SOURCES, f"SELECT *, CURRENT_TIMESTAMP() AS date_maj FROM UNNEST([{sources}])")

    etapes = _entonnoir()
    for etape, libelle, nb_dpe in etapes:
        logger.info("Entonnoir %d. %s : %d DPE", etape, libelle, nb_dpe)
    lignes = ", ".join(
        f"STRUCT({etape} AS etape, {_litteral(libelle)} AS libelle, {nb_dpe} AS nb_dpe)"
        for etape, libelle, nb_dpe in etapes
    )
    return _creer_table(TABLE_ENTONNOIR, f"SELECT *, CURRENT_TIMESTAMP() AS date_maj FROM UNNEST([{lignes}])")
