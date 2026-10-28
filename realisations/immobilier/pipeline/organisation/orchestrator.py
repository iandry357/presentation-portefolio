"""Nouvelle organisation Immobilier : vues « tableau brut », cubes DVF, Bâtiment, Croisé et loyers, table des paramètres (BigQuery).

S'exécute en LOCAL dans le venv scripts/venv-explore, PAS dans Docker.
Depuis realisations/immobilier, venv activé :
    python -m pipeline.organisation.orchestrator [--livraison 2026-10] [--departement 75]
                                                 [--debut 2025-05-01] [--fin AAAA-MM-JJ]
                                                 [--etape vues|cubes|tout]
Prérequis : pipeline/.env et gcp_sa_immobilier.json (réutilisés de la V1), tables dvf_etalab, bdnb_batiment_groupe,
bdnb_batiment_attributs, bdnb_rel_batiment_adresse, bdnb_adresse, bdnb_dpe_logement, bdnb_rel_dpe_batiment, dpe_typologie_ademe
et vues dvf_etalab_ventes_logement, dvf_etalab_ventes_batiment, loyers_ventes déjà construites.
"""
import argparse
import logging
import time
from datetime import date

from pipeline.organisation import cube_batiment, cube_croise, cube_dpe, cube_dvf, cube_loyers, qualite, sources
from pipeline.organisation.brut import construire_vues
from pipeline.organisation.config import DATE_DEBUT, DATE_FIN, DEPARTEMENT, LIVRAISON
from pipeline.organisation.parametres import ecrire

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s : %(message)s")
logger = logging.getLogger("orchestrator_organisation")


def _date(texte):
    """Date au format AAAA-MM-JJ ; refus d'un autre format avant toute requête."""
    return date.fromisoformat(texte).isoformat()


def main():
    parser = argparse.ArgumentParser(description="Nouvelle organisation Immobilier : vues brutes et cubes vers BigQuery")
    parser.add_argument("--livraison", default=LIVRAISON, help="livraison DVF Etalab lue (défaut : config.py)")
    parser.add_argument("--departement", default=DEPARTEMENT, help="code du département (défaut : config.py)")
    parser.add_argument("--debut", default=DATE_DEBUT, type=_date, help="début de la période, inclus (défaut : config.py)")
    parser.add_argument(
        "--fin", default=DATE_FIN, type=_date,
        help="fin de la période, incluse (défaut : config.py ; absent = jusqu'aux dernières données)",
    )
    parser.add_argument(
        "--etape", choices=["vues", "cubes", "sources", "tout"], default="tout",
        help="vues brutes seules ; cubes seuls, suivis de la table des paramètres ; sources et qualité seules (les cubes doivent exister) ; ou tout (défaut)",
    )
    args = parser.parse_args()

    debut = time.time()
    if args.etape in ("vues", "tout"):
        construire_vues()

    if args.etape in ("cubes", "tout"):
        cube_dvf.construire(args.livraison, args.departement, args.debut, args.fin)
        cube_batiment.construire()
        cube_croise.construire_ventes(args.livraison, args.departement, args.debut, args.fin)
        cube_dpe.construire(args.debut, args.fin)
        cube_loyers.construire(args.livraison, args.departement, args.debut, args.fin)
        ecrire(args.livraison, args.departement, args.debut, args.fin)

    if args.etape in ("sources", "tout"):
        sources.construire()
        qualite.construire()


    logger.info("Terminé (%.0f s)", time.time() - debut)


if __name__ == "__main__":
    main()
