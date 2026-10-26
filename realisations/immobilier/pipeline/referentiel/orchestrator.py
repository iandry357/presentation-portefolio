"""Pipeline du référentiel bailleur : collecte (PISTE, BOFiP), transformation en chunks, validation, chargement (ChromaDB + BigQuery).

S'exécute en LOCAL dans le venv scripts/venv-explore, PAS dans Docker. Depuis realisations/immobilier, venv activé :
    python -m pipeline.referentiel.orchestrator [--etape collecte|transformation|validation|chargement|tout] [--force]
                                                [--piste-env sandbox|production] [--vers chroma|bigquery|tout] [--dry-run]
Rafraîchir le corpus : --etape collecte --force, puis --etape tout (sans --force, une collecte existante est réutilisée).
Prérequis : pipeline/.env (PISTE_*, CHROMA_*, MISTRAL_API_KEY) et gcp_sa_immobilier.json.
"""
import argparse
import logging
import time

from pipeline.referentiel.collecte_bofip import collecter as collecter_bofip
from pipeline.referentiel.collecte_piste import collecter as collecter_piste
from pipeline.referentiel.loader import charger
from pipeline.referentiel.transformation import transformer
from pipeline.referentiel.validation import valider

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s : %(message)s")
logger = logging.getLogger("orchestrator_referentiel")

ETAPES = ["collecte", "transformation", "validation", "chargement"]


def main():
    parser = argparse.ArgumentParser(description="Corpus du référentiel bailleur : collecte, chunks, validation, chargement")
    parser.add_argument(
        "--etape", choices=[*ETAPES, "tout"], default="tout",
        help="une étape seule (collecte = PISTE puis BOFiP) ou toutes dans l'ordre (défaut)",
    )
    parser.add_argument("--force", action="store_true", help="recollecter même si les fichiers bruts existent")
    parser.add_argument("--piste-env", choices=["sandbox", "production"], default=None, help="force l'environnement PISTE (défaut : .env)")
    parser.add_argument("--vers", choices=["chroma", "bigquery", "tout"], default="tout", help="cible du chargement (défaut : les deux)")
    parser.add_argument("--dry-run", action="store_true", help="collecte, transformation et validation, sans chargement")
    args = parser.parse_args()

    debut = time.time()
    etapes = ETAPES if args.etape == "tout" else [args.etape]
    if "collecte" in etapes:
        collecter_piste(args.force, args.piste_env)
        collecter_bofip(args.force)
    if "transformation" in etapes:
        transformer()
    if "validation" in etapes:
        logger.info("Validation : %s", valider())
    if "chargement" in etapes:
        if args.dry_run:
            logger.info("--dry-run : chargement ignoré")
        else:
            logger.info("Chargement : %s", charger(etape=args.vers))
    logger.info("Terminé (%.0f s)", time.time() - debut)


if __name__ == "__main__":
    main()
