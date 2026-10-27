import re

import polars as pl

from pipeline.bdnb_complement.config import DOSSIER_CHARGEMENT, DOSSIER_PARQUET, MOTIF_COLONNES_INTERDITES, TABLES


def selection(table):
    """Sélection d'une table cible (LazyFrame) : les seules colonnes de la liste blanche, jamais une colonne interdite."""
    config = TABLES[table]
    interdites = [c for c in config["colonnes"] if re.search(MOTIF_COLONNES_INTERDITES, c, re.IGNORECASE)]
    if interdites:
        raise ValueError(f"{table} : colonnes interdites dans la liste blanche : {interdites}")
    return pl.scan_parquet(DOSSIER_PARQUET / f"{config['source']}.parquet").select(config["colonnes"])


def ecrire_parquet(table):
    """Écrit la sélection dans un Parquet temporaire (écriture puis renommage) et retourne son chemin."""
    DOSSIER_CHARGEMENT.mkdir(parents=True, exist_ok=True)
    cible = DOSSIER_CHARGEMENT / f"{table}.parquet"
    temporaire = DOSSIER_CHARGEMENT / f"{table}.parquet.tmp"
    selection(table).sink_parquet(temporaire)
    temporaire.replace(cible)
    return cible
