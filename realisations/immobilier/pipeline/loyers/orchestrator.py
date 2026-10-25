"""Chargement des loyers de référence de Paris (encadrement des loyers) : téléchargement, typage et contrôles, puis BigQuery.

S'exécute en LOCAL dans le venv scripts/venv-explore, PAS dans Docker (les données ne sont pas embarquées dans l'image).
Depuis realisations/immobilier, venv activé :
    python -m pipeline.loyers.orchestrator [--livraison 2026-10] [--departement 75]
                                           [--etape telechargement|chargement|rattachement|tout] [--dry-run] [--force]
Prérequis : pipeline/.env et gcp_sa_immobilier.json (réutilisés de la V1).
"""
import argparse
import logging
import time

from pipeline.loyers.config import TABLE_REFERENCE
from pipeline.loyers.config import DEPARTEMENT, LIVRAISON, TABLE_REFERENCE
from pipeline.loyers.loader import charger
from pipeline.loyers.rattachement import rattacher, valider
from pipeline.loyers.telechargement import preparer
from pipeline.loyers.transformation import construire_parquet
from pipeline.loyers.loader import charger
from pipeline.loyers.telechargement import preparer
from pipeline.loyers.transformation import construire_parquet

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s : %(message)s")
logger = logging.getLogger("orchestrator_loyers")


def main():
    parser = argparse.ArgumentParser(description="Chargement des loyers de référence de Paris vers BigQuery")
    parser.add_argument("--livraison", default=LIVRAISON, help="livraison DVF Etalab à rattacher (défaut : config.py)")
    parser.add_argument("--departement", default=DEPARTEMENT, help="code du département (défaut : config.py)")
    parser.add_argument(
        "--etape", choices=["telechargement", "chargement", "rattachement", "tout"], default="tout",
        help="téléchargement et contrôle du CSV seuls ; chargement des loyers ; rattachement des ventes et validation ; "
             "ou chargement puis rattachement (défaut)",
    )
    parser.add_argument("--dry-run", action="store_true", help="téléchargement, typage et contrôles, sans écriture BigQuery")
    parser.add_argument("--force", action="store_true", help="retélécharger le CSV même s'il existe")
    args = parser.parse_args()

    debut = time.time()
    if args.etape in ("telechargement", "chargement", "tout"):
        resultat = preparer(args.force)
        if args.etape == "telechargement":
            logger.info("Fichier prêt (%.0f s)", time.time() - debut)
            return

        chemin_reference, chemin_quartiers, stats = construire_parquet(resultat)
        logger.info(
            "Parquet : %d lignes de référence (%d à %d), %d quartiers (%s, %s)",
            stats["lignes"], stats["annee_min"], stats["annee_max"], stats["quartiers"], chemin_reference.name, chemin_quartiers.name,
        )
        if args.dry_run:
            logger.info("--dry-run : chargement BigQuery et rattachement ignorés (%.0f s)", time.time() - debut)
            return

        nb = charger(chemin_reference, chemin_quartiers, resultat, stats)
        logger.info("%d lignes dans %s (%.0f s)", nb, TABLE_REFERENCE, time.time() - debut)

    if args.etape in ("rattachement", "tout"):
        if args.dry_run:
            logger.info("--dry-run : rattachement ignoré")
            return
        rattacher(args.livraison, args.departement)
        valider(args.livraison, args.departement)
        logger.info("Rattachement et validation terminés (%.0f s)", time.time() - debut)



if __name__ == "__main__":
    main()
