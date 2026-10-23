import io
import json
import logging
import time
from datetime import datetime

import polars as pl
import requests
from google.cloud import bigquery

from pipeline.analyse.config import (
    API_ADEME, BQ_DATASET, CHAMP_DEPARTEMENT_ADEME, CHAMPS_ADEME, DEPARTEMENT, DOSSIER_TYPOLOGIE, GCP_PROJECT_ID,
    GCP_SA_KEY_PATH, MAX_TENTATIVES, PIECES_MAX, TABLE_TYPOLOGIE, TAILLE_PAGE, TIMEOUT,
)

logger = logging.getLogger(__name__)


def _get(url, params=None):
    for tentative in range(1, MAX_TENTATIVES + 1):
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            if tentative == MAX_TENTATIVES:
                raise
            logger.warning("Tentative %d/%d échouée : %s", tentative, MAX_TENTATIVES, e)
            time.sleep(5 * tentative)


def telecharger(force=False):
    """DPE avec typologie dans typologie_dpe/<date du jour>/typologie.csv (extraction du jour réutilisée sauf --force).
    Retourne le dossier de l'extraction."""
    dossier = DOSSIER_TYPOLOGIE / datetime.now().strftime("%Y-%m-%d")
    cible = dossier / "typologie.csv"
    if cible.exists() and not force:
        logger.info("Extraction du jour déjà présente : %s", cible)
        return dossier

    qs = f"{CHAMP_DEPARTEMENT_ADEME}:{DEPARTEMENT} AND _exists_:typologie_logement"
    reponse = _get(f"{API_ADEME}/lines", {"size": TAILLE_PAGE, "select": ",".join(CHAMPS_ADEME), "qs": qs})
    total = reponse["total"]
    lignes = []
    while True:
        lignes.extend({c: r.get(c) for c in CHAMPS_ADEME} for r in reponse["results"])
        logger.info("%d / %d", len(lignes), total)
        if not reponse.get("next") or not reponse["results"]:
            break
        reponse = _get(reponse["next"])
    if len(lignes) != total:
        raise ValueError(f"{len(lignes)} lignes téléchargées pour {total} annoncées par l'API")

    dossier.mkdir(parents=True, exist_ok=True)
    temporaire = cible.with_suffix(".csv.tmp")
    pl.DataFrame(lignes, schema={c: pl.String for c in CHAMPS_ADEME}).write_csv(temporaire)
    temporaire.replace(cible)
    (dossier / "manifeste.json").write_text(json.dumps({
        "api": API_ADEME, "qs": qs, "champs": CHAMPS_ADEME, "lignes": len(lignes),
        "extrait_le": datetime.now().isoformat(timespec="seconds"),
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("%d DPE avec typologie téléchargés dans %s", len(lignes), cible)
    return dossier


def lire(dossier):
    """DPE avec typologie : numéro normalisé, pièces (chiffre de « T3 », plafonné à PIECES_MAX), date d'établissement.
    Typage strict : un numéro vide ou une typologie hors « T<chiffre> » arrête le traitement."""
    brut = pl.read_csv(dossier / "typologie.csv", infer_schema_length=0)
    if brut["numero_dpe"].null_count():
        raise ValueError(f"{brut['numero_dpe'].null_count()} numéros de DPE vides dans {dossier / 'typologie.csv'}")
    df = brut.select(
        pl.col("numero_dpe").str.strip_chars().str.to_uppercase().alias("identifiant_dpe"),
        pl.col("typologie_logement").str.strip_chars().alias("typologie"),
        pl.col("date_etablissement_dpe").str.slice(0, 10).str.to_date("%Y-%m-%d", strict=False).alias("date_etablissement"),
    ).unique("identifiant_dpe")

    inattendues = df.filter(~pl.col("typologie").str.contains(r"^T\d", literal=False).fill_null(False))
    if len(inattendues):
        valeurs = inattendues["typologie"].unique().to_list()
        raise ValueError(f"{len(inattendues)} DPE avec une typologie inattendue : {valeurs[:10]}")
    if df["date_etablissement"].null_count():
        logger.warning("%d DPE sans date d'établissement lisible", df["date_etablissement"].null_count())

    return df.with_columns(
        pl.col("typologie").str.extract(r"^T(\d)", 1).cast(pl.Int64).clip(upper_bound=PIECES_MAX).alias("pieces"),
        pl.lit(datetime.strptime(dossier.name, "%Y-%m-%d").date()).alias("extraction"),
    ).select("identifiant_dpe", "typologie", "pieces", "date_etablissement", "extraction")


def charger(df):
    """Remplace la table dpe_typologie_ademe (WRITE_TRUNCATE) et contrôle le nombre de lignes."""
    client = bigquery.Client.from_service_account_json(str(GCP_SA_KEY_PATH), project=GCP_PROJECT_ID)
    tampon = io.BytesIO()
    df.write_parquet(tampon)
    tampon.seek(0)
    config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        clustering_fields=["identifiant_dpe"],
    )
    job = client.load_table_from_file(tampon, f"{GCP_PROJECT_ID}.{BQ_DATASET}.{TABLE_TYPOLOGIE}", job_config=config)
    job.result()
    if job.output_rows != len(df):
        raise ValueError(f"{TABLE_TYPOLOGIE} : {job.output_rows} lignes chargées pour {len(df)} attendues")
    logger.info("Table %s : %d lignes", TABLE_TYPOLOGIE, job.output_rows)
    return job.output_rows
