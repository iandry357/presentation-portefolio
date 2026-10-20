import argparse
import logging
import time
from collections import Counter

import pandas as pd

from pipeline.collectors.dpe_collector import collecter_dpe
from pipeline.collectors.dvf_collector import collecter_dvf
from pipeline.config import (
    BQ_TABLE_DPE, BQ_TABLE_DVF, DPE_CACHE_DIR, DPE_PAGES_ECHANTILLON, DPE_SCHEMA,
    DVF_CACHE_DIR, DVF_SCHEMA, NULL_MARKER,
)
from pipeline.loaders.bigquery_loader import charger_csv
from pipeline.loaders.aggregations import construire_agg_dpe, construire_agg_dvf
from pipeline.transformation.dpe_transform import transformer_dpe
from pipeline.transformation.dvf_transform import transformer_dvf
from pipeline.validators.quality import valider_dpe, valider_dvf


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s : %(message)s")
logger = logging.getLogger("orchestrator")


def executer_dpe(echantillon, reprendre):
    debut = time.time()
    collecter_dpe(echantillon=echantillon, reprendre=reprendre)

    pages = sorted(DPE_CACHE_DIR.glob("page_*.csv"))
    if not pages:
        raise RuntimeError("Aucune page DPE en cache")
    sortie = DPE_CACHE_DIR / "dpe_logements.csv"
    sortie.unlink(missing_ok=True)

    numeros_vus, rejets = set(), Counter()
    nb_collecte, nb_valide = 0, 0
    for i, page in enumerate(pages):
        df = pd.read_csv(page, dtype=str, na_values=[""], keep_default_na=False)
        nb_collecte += len(df)
        df, rejets_page = valider_dpe(transformer_dpe(df), numeros_vus)
        rejets.update(rejets_page)
        df.to_csv(sortie, mode="a", header=(i == 0), index=False, na_rep=NULL_MARKER)
        nb_valide += len(df)

    nb_charge = charger_csv(sortie, BQ_TABLE_DPE, DPE_SCHEMA)
    construire_agg_dpe()

    logger.info(
        "DPE (%s) : collecté=%d validé=%d rejeté=%d %s chargé=%d (%.0f s)",
        "échantillon" if echantillon else "complet",
        nb_collecte, nb_valide, nb_collecte - nb_valide, dict(rejets), nb_charge, time.time() - debut,
    )


def executer_dvf():
    debut = time.time()
    collecter_dvf()

    sortie = DVF_CACHE_DIR / "dvf_mutations.csv"
    sortie.unlink(missing_ok=True)

    rejets = Counter()
    nb_brut, nb_ventes, nb_valide = 0, 0, 0
    for i, fichier in enumerate(sorted(DVF_CACHE_DIR.glob("*.csv.gz"))):
        df = pd.read_csv(fichier, compression="gzip", dtype=str, na_values=[""], keep_default_na=False)
        nb_brut += len(df)
        df, ecartees = transformer_dvf(df)
        nb_ventes += len(df)
        rejets.update(ecartees)
        df, rejets_annee = valider_dvf(df)
        rejets.update(rejets_annee)
        df.to_csv(sortie, mode="a", header=(i == 0), index=False, na_rep=NULL_MARKER)
        nb_valide += len(df)
        logger.info("DVF %s : %d ventes de logement, %d validées", fichier.name[:4], nb_ventes, nb_valide)

    nb_charge = charger_csv(sortie, BQ_TABLE_DVF, DVF_SCHEMA)
    construire_agg_dvf()

    logger.info(
        "DVF : lignes brutes=%d ventes de logement=%d validé=%d rejeté=%d %s chargé=%d (%.0f s)",
        nb_brut, nb_ventes, nb_valide, nb_ventes - nb_valide, dict(rejets), nb_charge, time.time() - debut,
    )


def main():
    parser = argparse.ArgumentParser(description="Pipeline Immobilier")
    parser.add_argument("--source", choices=["dpe", "dvf", "all", "agg"], default="dpe")


    parser.add_argument(
        "--echantillon", type=int, nargs="?", const=DPE_PAGES_ECHANTILLON, default=None,
        help="Échantillon aléatoire de N pages (défaut sans valeur : DPE_PAGES_ECHANTILLON)",
    )
    parser.add_argument("--reprendre", action="store_true", help="Reprend une collecte complète interrompue")
    args = parser.parse_args()

    if args.source in ("dpe", "all"):
        executer_dpe(args.echantillon, args.reprendre)
    if args.source in ("dvf", "all"):
        executer_dvf()
    if args.source == "agg":
        construire_agg_dpe()
        construire_agg_dvf()




if __name__ == "__main__":
    main()
