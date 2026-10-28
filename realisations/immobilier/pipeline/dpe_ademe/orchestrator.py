"""Collecte des DPE ADEME d'un département depuis une date vers BigQuery (table org_dpe_ademe), sans toucher à la V1 (dpe_logements).

S'exécute en LOCAL dans le venv scripts/venv-explore, PAS dans Docker.
Depuis realisations/immobilier, venv activé :
    python -m pipeline.dpe_ademe.orchestrator --essai
    python -m pipeline.dpe_ademe.orchestrator [--departement 75] [--depuis 2025-05-01]
                                              [--etape collecte|chargement|tout] [--reprendre]
Prérequis : pipeline/.env et gcp_sa_immobilier.json (réutilisés de la V1).
"""
import argparse
import logging
import time
from datetime import date

from pipeline.dpe_ademe.chargement import charger, preparer, resumer_essai
from pipeline.dpe_ademe.collecte import collecter
from pipeline.dpe_ademe.config import DATE_DEBUT_COLLECTE, DEPARTEMENT, DOSSIER_CACHE, FICHIER_TERMINE, NB_PAGES_ESSAI

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s : %(message)s")
logger = logging.getLogger("orchestrator_dpe_ademe")


def _date(texte):
    """Date au format AAAA-MM-JJ ; refus d'un autre format avant toute requête."""
    return date.fromisoformat(texte).isoformat()


def _total_collecte():
    """Total collecté enregistré à la fin de la dernière collecte complète."""
    marqueur = DOSSIER_CACHE / FICHIER_TERMINE
    if not marqueur.exists():
        raise RuntimeError("Collecte non terminée : lancer --etape collecte (avec --reprendre si elle a été interrompue)")
    return int(marqueur.read_text())


def main():
    parser = argparse.ArgumentParser(description="DPE ADEME (collecte depuis une date) vers BigQuery")
    parser.add_argument("--departement", default=DEPARTEMENT, help="code du département (défaut : config.py)")
    parser.add_argument(
        "--depuis", default=DATE_DEBUT_COLLECTE, type=_date,
        help="début de la collecte, inclus (défaut : config.py) ; à garder identique pour --reprendre",
    )
    parser.add_argument(
        "--etape", choices=["collecte", "chargement", "tout"], default="tout",
        help="collecte seule ; chargement seul (la collecte doit être terminée) ; ou les deux (défaut)",
    )
    parser.add_argument("--reprendre", action="store_true", help="reprend une collecte interrompue")
    parser.add_argument(
        "--essai", action="store_true",
        help=f"collecte {NB_PAGES_ESSAI} pages de la première tranche, affiche valeurs et anomalies, n'écrit rien dans BigQuery",
    )
    args = parser.parse_args()

    debut = time.time()
    if args.essai:
        collecter(args.departement, args.depuis, nb_pages=NB_PAGES_ESSAI)
        resumer_essai()
        logger.info("Essai terminé (%.0f s) : rien n'a été écrit dans BigQuery", time.time() - debut)
        return

    if args.etape in ("collecte", "tout"):
        collecter(args.departement, args.depuis, reprendre=args.reprendre)

    if args.etape in ("chargement", "tout"):
        chemin, nb, illisibles = preparer(_total_collecte())
        logger.info("Valeurs illisibles par colonne : %s", {nom: n for nom, n in illisibles.items() if n} or "aucune")
        charger(chemin, nb)

    logger.info("Terminé (%.0f s)", time.time() - debut)


if __name__ == "__main__":
    main()
