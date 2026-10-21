"""Chargement BDNB (Paris 75) : Parquet locaux, sélection, puis BigQuery (tables bdnb_*).

S'exécute en LOCAL dans le venv scripts/venv-explore, PAS dans Docker (les données BDNB ne sont pas embarquées dans l'image).
Depuis realisations/immobilier, venv activé :
    python -m pipeline.bdnb.orchestrator [--tables t1 t2 ...] [--dry-run]
Prérequis : pipeline/.env et gcp_sa_immobilier.json (réutilisés de la V1), Parquet produits par scripts/convert_bdnb_parquet.py.
"""
import argparse
import logging
import time

import polars as pl

from pipeline.bdnb.config import TABLES
from pipeline.bdnb.loader import charger_parquet
from pipeline.bdnb.selection import ecrire_parquet

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s : %(message)s")
logger = logging.getLogger("orchestrator_bdnb")


def controler(table, chemin):
    """Compare lignes et colonnes du Parquet sélectionné aux valeurs attendues (lignes None = relevé seulement)."""
    lf = pl.scan_parquet(chemin)
    lignes = lf.select(pl.len()).collect().item()
    colonnes = len(lf.collect_schema())
    attendu = TABLES[table]

    ecarts = []
    if attendu["lignes"] is not None and lignes != attendu["lignes"]:
        ecarts.append(f"{lignes} lignes au lieu de {attendu['lignes']}")
    if colonnes != attendu["colonnes"]:
        ecarts.append(f"{colonnes} colonnes au lieu de {attendu['colonnes']}")
    if ecarts:
        raise ValueError(f"{table} : " + ", ".join(ecarts))
    if attendu["lignes"] is None:
        logger.info("%s : nombre de lignes non contrôlé (valeur attendue à renseigner dans config.py)", table)
    return lignes, colonnes


def executer(table, dry_run):
    debut = time.time()
    chemin = ecrire_parquet(table)
    lignes, colonnes = controler(table, chemin)

    if dry_run:
        logger.info(
            "%s : sélectionné=%d lignes, %d colonnes, chargement ignoré (--dry-run) (%.0f s)",
            table, lignes, colonnes, time.time() - debut,
        )
        return

    nb_charge = charger_parquet(chemin, table)
    if nb_charge != lignes:
        raise ValueError(f"{table} : {nb_charge} lignes chargées pour {lignes} sélectionnées")
    logger.info("%s : sélectionné=%d colonnes=%d chargé=%d (%.0f s)", table, lignes, colonnes, nb_charge, time.time() - debut)


def main():
    parser = argparse.ArgumentParser(description="Chargement BDNB vers BigQuery")
    parser.add_argument("--tables", nargs="+", choices=list(TABLES), default=list(TABLES), help="tables à traiter (défaut : toutes)")
    parser.add_argument("--dry-run", action="store_true", help="sélection et contrôle, sans chargement BigQuery")
    args = parser.parse_args()

    for table in args.tables:
        executer(table, args.dry_run)


if __name__ == "__main__":
    main()
