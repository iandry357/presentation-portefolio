"""Chargement du DVF Etalab (livraison versionnée) : téléchargement et filtre du département, typage, puis BigQuery.

S'exécute en LOCAL dans le venv scripts/venv-explore, PAS dans Docker (les données ne sont pas embarquées dans l'image).
Depuis realisations/immobilier, venv activé :
    python -m pipeline.dvf_etalab.orchestrator [--livraison 2026-10] [--departement 75]
                                               [--etape telechargement|chargement|rattachement|tout] [--dry-run] [--force]
Prérequis : pipeline/.env et gcp_sa_immobilier.json (réutilisés de la V1).
"""
import argparse
import logging
import time

from pipeline.dvf_etalab.config import DEPARTEMENT, LIVRAISON, LIVRAISONS
from pipeline.dvf_etalab.loader import charger
from pipeline.dvf_etalab.rattachement import rattacher, valider
from pipeline.dvf_etalab.telechargement import preparer
from pipeline.dvf_etalab.transformation import construire_parquet

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s : %(message)s")
logger = logging.getLogger("orchestrator_dvf_etalab")


def main():
    parser = argparse.ArgumentParser(description="Chargement du DVF Etalab vers BigQuery")
    parser.add_argument("--livraison", choices=list(LIVRAISONS), default=LIVRAISON, help="livraison à charger")
    parser.add_argument("--departement", default=DEPARTEMENT, help="code du département (défaut : config.py)")
    parser.add_argument(
        "--etape", choices=["telechargement", "chargement", "rattachement", "tout"], default="tout",
        help="téléchargement et filtre seuls ; chargement BigQuery ; rattachement aux bâtiments et validation ; "
             "ou chargement puis rattachement (défaut)",
    )
    parser.add_argument("--dry-run", action="store_true", help="téléchargement, filtre, typage et contrôles, sans écriture BigQuery ni rattachement")
    parser.add_argument("--force", action="store_true", help="retélécharger et refiltrer même si les fichiers existent")
    args = parser.parse_args()

    debut = time.time()
    if args.etape in ("telechargement", "chargement", "tout"):
        resultats = preparer(args.livraison, args.departement, args.force)
        if sum(r["lignes"] for r in resultats.values()) == 0:
            raise ValueError(f"Aucune ligne pour le département {args.departement}")
        if args.etape == "telechargement":
            logger.info("Fichiers prêts (%.0f s)", time.time() - debut)
            return

        chemin, stats = construire_parquet(args.livraison, args.departement, resultats)
        logger.info(
            "Parquet %s : %d lignes, %d colonnes, mutations du %s au %s",
            chemin.name, stats["lignes"], stats["colonnes"], stats["date_min"], stats["date_max"],
        )
        if args.dry_run:
            logger.info("--dry-run : chargement BigQuery et rattachement ignorés (%.0f s)", time.time() - debut)
            return

        nb = charger(chemin, args.livraison, args.departement, stats, resultats)
        logger.info(
            "Livraison %s, département %s : %d lignes dans dvf_etalab (%.0f s)",
            args.livraison, args.departement, nb, time.time() - debut,
        )

    if args.etape in ("rattachement", "tout"):
        if args.dry_run:
            logger.info("--dry-run : rattachement ignoré")
            return
        rattacher(args.livraison, args.departement)
        valider(args.livraison, args.departement)
        logger.info("Rattachement et validation terminés (%.0f s)", time.time() - debut)


if __name__ == "__main__":
    main()
