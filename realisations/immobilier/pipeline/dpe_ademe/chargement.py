import logging
from collections import Counter

import pandas as pd
from google.cloud import bigquery

from pipeline.dpe_ademe.config import (
    BQ_DATASET, CHAMP_CLE, CHAMPS_VALEURS_ESSAI, CLUSTER, COLONNE_PARTITION, DOSSIER_CACHE, FICHIER_SORTIE,
    GCP_PROJECT_ID, GCP_SA_KEY_PATH, NULL_MARKER, SCHEMA, TABLE_DPE, TABLE_TRAVAIL,
)
from pipeline.dpe_ademe.transformation import COLONNES_DATE, transformer

logger = logging.getLogger(__name__)


def _client():
    return bigquery.Client.from_service_account_json(str(GCP_SA_KEY_PATH), project=GCP_PROJECT_ID)


def _table(nom):
    return f"`{GCP_PROJECT_ID}.{BQ_DATASET}.{nom}`"


def _lire_pages():
    """Les pages du cache, une à une, lues en texte (la transformation fait le typage)."""
    for page in sorted(DOSSIER_CACHE.glob("page_*.csv")):
        yield pd.read_csv(page, dtype=str, na_values=[""], keep_default_na=False)


def preparer(total):
    """Transforme les pages du cache en un CSV unique (FICHIER_SORTIE). Aucune ligne écartée ; arrêt si une clé est vide ou en
    double, ou si le nombre de lignes diffère du total annoncé par l'API. Retourne (chemin, nombre de lignes, illisibles)."""
    sortie = DOSSIER_CACHE / FICHIER_SORTIE
    sortie.unlink(missing_ok=True)
    vus, illisibles, nb = set(), Counter(), 0
    for i, brut in enumerate(_lire_pages()):
        df, illisibles_page = transformer(brut)
        illisibles.update(illisibles_page)
        cles = df[CHAMP_CLE]
        if cles.isna().any():
            raise ValueError(f"Page {i + 1} : {int(cles.isna().sum())} DPE sans {CHAMP_CLE}")
        if cles.duplicated().any() or cles.isin(vus).any():
            raise ValueError(f"Page {i + 1} : {CHAMP_CLE} en double (page relue après une reprise ?)")
        vus.update(cles)
        df.to_csv(sortie, mode="a", header=(i == 0), index=False, na_rep=NULL_MARKER)
        nb += len(df)
    if nb == 0:
        raise RuntimeError("Aucune page DPE en cache")
    if nb != total:
        raise ValueError(f"{nb} DPE collectés pour {total} annoncés par l'API")
    logger.info("CSV préparé : %d lignes, %s", nb, sortie)
    return sortie, nb, illisibles


def charger(chemin_csv, nb_attendu):
    """Charge le CSV dans la table de travail, puis remplace la table finale (partition par mois, cluster par arrondissement)."""
    client = _client()
    travail = f"{GCP_PROJECT_ID}.{BQ_DATASET}.{TABLE_TRAVAIL}"
    config = bigquery.LoadJobConfig(
        schema=[bigquery.SchemaField(nom, type_bq) for nom, type_bq in SCHEMA],
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        null_marker=NULL_MARKER,
        allow_quoted_newlines=True,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    with open(chemin_csv, "rb") as f:
        job = client.load_table_from_file(f, travail, job_config=config)
    job.result()
    if job.output_rows != nb_attendu:
        raise ValueError(f"{TABLE_TRAVAIL} : {job.output_rows} lignes chargées pour {nb_attendu} préparées")
    logger.info("Table de travail %s chargée : %d lignes", TABLE_TRAVAIL, job.output_rows)

    client.query(f"""
        CREATE OR REPLACE TABLE {_table(TABLE_DPE)}
        PARTITION BY DATE_TRUNC({COLONNE_PARTITION}, MONTH) CLUSTER BY {", ".join(CLUSTER)} AS
        SELECT * FROM {_table(TABLE_TRAVAIL)}
    """).result()
    client.delete_table(travail, not_found_ok=True)
    _verifier(client, nb_attendu)


def _verifier(client, nb_attendu):
    """Arrêt au premier écart : autant de lignes que de clés distinctes, égal au nombre préparé."""
    ligne = dict(next(iter(client.query(f"""
        SELECT COUNT(*) AS lignes, COUNT(DISTINCT {CHAMP_CLE}) AS cles,
               MIN({COLONNE_PARTITION}) AS premiere_date, MAX({COLONNE_PARTITION}) AS derniere_date,
               COUNTIF(arrondissement IS NULL) AS sans_arrondissement,
               COUNTIF(numero_dpe_remplace IS NOT NULL) AS remplacants
        FROM {_table(TABLE_DPE)}
    """).result())))
    if ligne["lignes"] != nb_attendu or ligne["cles"] != nb_attendu:
        raise ValueError(f"{TABLE_DPE} : {ligne['lignes']} lignes et {ligne['cles']} clés distinctes pour {nb_attendu} attendues")
    logger.info("Table %s : %s", TABLE_DPE, ligne)


def resumer_essai():
    """Essai : transforme les pages en cache et affiche les valeurs et anomalies, sans BigQuery."""
    brut = pd.concat(list(_lire_pages()), ignore_index=True)
    df, illisibles = transformer(brut)
    print(f"\n== Essai : {len(df)} DPE, {df[CHAMP_CLE].nunique()} clés distinctes")
    print("sans arrondissement :", int(df["arrondissement"].isna().sum()))
    print("dates, de", df[COLONNE_PARTITION].min(), "à", df[COLONNE_PARTITION].max())
    print("valeurs illisibles par colonne :", {nom: n for nom, n in illisibles.items() if n} or "aucune")
    print("\n== Longueur des dates brutes (un seul format attendu)")
    for col in COLONNES_DATE:
        print(f"{col} :", brut[col].dropna().str.len().value_counts().to_dict())
    for champ in CHAMPS_VALEURS_ESSAI:
        print(f"\n== {champ}")
        print(df[champ].value_counts(dropna=False).to_string())
