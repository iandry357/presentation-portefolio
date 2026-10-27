"""Chargement BDNB complémentaire (Paris 75) : Parquet locaux, liste blanche de colonnes, puis BigQuery (tables bdnb_*).

S'exécute en LOCAL dans le venv scripts/venv-explore, PAS dans Docker (les données BDNB ne sont pas embarquées dans l'image).
Depuis realisations/immobilier, venv activé :
    python -m pipeline.bdnb_complement.orchestrator [--etape chargement|attributs|tout] [--tables t1 t2 ...] [--dry-run]
Prérequis : pipeline/.env et gcp_sa_immobilier.json (réutilisés de la V1), Parquet produits par scripts/convert_bdnb_parquet.py
(--tables batiment_groupe_ffo_bat batiment_groupe_bdtopo_bat batiment_groupe_rnc batiment_groupe_risques
batiment_groupe_urbanisme parcelle_sitadel). Indépendant de pipeline/bdnb : ses tables et sa config ne sont pas touchées.
"""
import argparse
import logging
import time

import polars as pl

from pipeline.bdnb_complement.attributs import construire_batiments, construire_parcelles
from pipeline.bdnb_complement.config import TABLES
from pipeline.bdnb_complement.loader import charger_parquet
from pipeline.bdnb_complement.selection import ecrire_parquet

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s : %(message)s")
logger = logging.getLogger("orchestrator_bdnb_complement")


def controler(table, chemin):
    """Compare lignes et colonnes du Parquet sélectionné aux valeurs attendues et vérifie une ligne par clé."""
    lf = pl.scan_parquet(chemin)
    lignes = lf.select(pl.len()).collect().item()
    colonnes = len(lf.collect_schema())
    attendu = TABLES[table]
    cle = attendu["cluster"][0]
    distinctes = lf.select(pl.col(cle).n_unique()).collect().item()

    ecarts = []
    if lignes != attendu["lignes"]:
        ecarts.append(f"{lignes} lignes au lieu de {attendu['lignes']}")
    if colonnes != len(attendu["colonnes"]):
        ecarts.append(f"{colonnes} colonnes au lieu de {len(attendu['colonnes'])}")
    if distinctes != lignes:
        ecarts.append(f"{distinctes} {cle} distincts pour {lignes} lignes (une ligne par clé attendue)")
    if ecarts:
        raise ValueError(f"{table} : " + ", ".join(ecarts))
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
    parser = argparse.ArgumentParser(description="Chargement BDNB complémentaire vers BigQuery")
    parser.add_argument(
        "--etape", choices=["chargement", "attributs", "tout"], default="chargement",
        help="chargement des tables bdnb_* (défaut), tables d'attributs (immeuble et parcelle), ou les deux dans cet ordre",
    )
    parser.add_argument("--tables", nargs="+", choices=list(TABLES), default=list(TABLES), help="tables à charger (défaut : toutes)")
    parser.add_argument("--dry-run", action="store_true", help="sélection et contrôle, sans écriture BigQuery")
    args = parser.parse_args()

    if args.etape in ("chargement", "tout"):
        for table in args.tables:
            executer(table, args.dry_run)
    if args.dry_run:
        logger.info("--dry-run : attributs non construits")
        return
    if args.etape in ("attributs", "tout"):
        construire_batiments()
        construire_parcelles()


if __name__ == "__main__":
    main()

