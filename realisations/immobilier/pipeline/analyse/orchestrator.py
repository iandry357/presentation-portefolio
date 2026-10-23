"""Cube d'analyse Immobilier BDNB : typologie ADEME (DPE avec pièces), puis agrégats ventes et DPE dans BigQuery.

S'exécute en LOCAL dans le venv scripts/venv-explore, PAS dans Docker.
Depuis realisations/immobilier, venv activé :
    python -m pipeline.analyse.orchestrator [--livraison 2026-10] [--departement 75]
                                            [--etape typologie|cube|tout] [--dry-run] [--force]
Prérequis : pipeline/.env et gcp_sa_immobilier.json (réutilisés de la V1), tables bdnb_*, dvf_etalab et
dvf_etalab_rattachement déjà chargées.
"""
import argparse
import logging
import time

from pipeline.analyse.config import DEPARTEMENT, LIVRAISON
from pipeline.analyse.cube import construire_dpe, construire_ventes
from pipeline.analyse.typologie import charger, lire, telecharger

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s : %(message)s")
logger = logging.getLogger("orchestrator_analyse")


def main():
    parser = argparse.ArgumentParser(description="Cube d'analyse Immobilier BDNB vers BigQuery")
    parser.add_argument("--livraison", default=LIVRAISON, help="livraison DVF Etalab lue (défaut : config.py)")
    parser.add_argument("--departement", default=DEPARTEMENT, help="code du département (défaut : config.py)")
    parser.add_argument(
        "--etape", choices=["typologie", "cube", "tout"], default="tout",
        help="typologie ADEME seule ; cube seul (la table dpe_typologie_ademe doit exister) ; ou les deux (défaut)",
    )
    parser.add_argument("--dry-run", action="store_true", help="téléchargement et lecture de la typologie, sans écriture BigQuery ni cube")
    parser.add_argument("--force", action="store_true", help="retélécharger la typologie même si l'extraction du jour existe")
    args = parser.parse_args()

    debut = time.time()
    if args.etape in ("typologie", "tout"):
        dossier = telecharger(args.force)
        df = lire(dossier)
        logger.info("Typologie : %d DPE, pièces de %d à %d", len(df), df["pieces"].min(), df["pieces"].max())
        if args.dry_run:
            logger.info("--dry-run : chargement BigQuery et cube ignorés (%.0f s)", time.time() - debut)
            return
        charger(df)

    if args.etape in ("cube", "tout"):
        if args.dry_run:
            logger.info("--dry-run : cube ignoré")
            return
        construire_ventes(args.livraison, args.departement)
        construire_dpe()
        logger.info("Cube terminé (%.0f s)", time.time() - debut)


if __name__ == "__main__":
    main()
