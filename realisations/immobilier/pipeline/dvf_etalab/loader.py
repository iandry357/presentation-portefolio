import logging

from google.cloud import bigquery

from pipeline.dvf_etalab.config import (
    BQ_DATASET, CLUSTER, COLONNE_FICHIER, COLONNE_LIVRAISON, COLONNES, GCP_PROJECT_ID, GCP_SA_KEY_PATH,
    LIVRAISONS, TABLE_DVF, TABLE_LIVRAISONS, TABLE_TRAVAIL,
)

logger = logging.getLogger(__name__)

COLONNES_TABLE = [COLONNE_LIVRAISON] + [nom for nom, _ in COLONNES] + [COLONNE_FICHIER]


def _client():
    return bigquery.Client.from_service_account_json(str(GCP_SA_KEY_PATH), project=GCP_PROJECT_ID)


def _table(nom):
    return f"`{GCP_PROJECT_ID}.{BQ_DATASET}.{nom}`"


def _litteral(valeur):
    """Texte SQL entre apostrophes (échappées avec un antislash, comme en GoogleSQL)."""
    return "'" + str(valeur).replace("\\", "\\\\").replace("'", "\\'") + "'"


def charger(chemin_parquet, livraison, departement, stats, resultats):
    """Charge le Parquet dans dvf_etalab sans toucher aux autres livraisons ni départements :
    le couple (livraison, département) est remplacé en une transaction. Retourne le nombre de lignes du couple."""
    client = _client()
    parametres = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("livraison", "STRING", livraison),
        bigquery.ScalarQueryParameter("departement", "STRING", departement),
    ])

    # 1. Table de travail (recréée à chaque chargement)
    config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        clustering_fields=CLUSTER,
    )
    with open(chemin_parquet, "rb") as f:
        job = client.load_table_from_file(f, f"{GCP_PROJECT_ID}.{BQ_DATASET}.{TABLE_TRAVAIL}", job_config=config)
    job.result()
    if job.output_rows != stats["lignes"]:
        raise ValueError(f"{TABLE_TRAVAIL} : {job.output_rows} lignes chargées pour {stats['lignes']} attendues")
    logger.info("Table de travail %s : %d lignes", TABLE_TRAVAIL, job.output_rows)

    # 2. Tables cibles, créées au premier chargement seulement
    client.query(
        f"CREATE TABLE IF NOT EXISTS {_table(TABLE_DVF)} CLUSTER BY {', '.join(CLUSTER)} "
        f"AS SELECT * FROM {_table(TABLE_TRAVAIL)} WHERE FALSE"
    ).result()
    client.query(f"""
        CREATE TABLE IF NOT EXISTS {_table(TABLE_LIVRAISONS)} (
            livraison STRING, code_departement STRING, fichier_source STRING, url STRING, sha1 STRING,
            taille_octets INT64, lignes INT64, publication DATE, periode_debut DATE, periode_fin DATE,
            date_chargement TIMESTAMP
        )
    """).result()

    # 3. Remplacement du couple (livraison, département), annulé en bloc au moindre échec
    colonnes = ", ".join(COLONNES_TABLE)
    fichiers = LIVRAISONS[livraison]["fichiers"]
    lignes_fichiers = ", ".join(
        f"STRUCT({_litteral(etiquette)} AS fichier_source, {_litteral(fichiers[etiquette]['url'])} AS url, "
        f"{_litteral(r['sha1'])} AS sha1, {r['taille_octets']} AS taille_octets, {r['lignes']} AS lignes)"
        for etiquette, r in resultats.items()
    )
    script = f"""
        BEGIN
          BEGIN TRANSACTION;
          DELETE FROM {_table(TABLE_DVF)} WHERE livraison = @livraison AND code_departement = @departement;
          INSERT INTO {_table(TABLE_DVF)} ({colonnes}) SELECT {colonnes} FROM {_table(TABLE_TRAVAIL)};
          DELETE FROM {_table(TABLE_LIVRAISONS)} WHERE livraison = @livraison AND code_departement = @departement;
          INSERT INTO {_table(TABLE_LIVRAISONS)} (
              livraison, code_departement, fichier_source, url, sha1, taille_octets, lignes,
              publication, periode_debut, periode_fin, date_chargement
          )
          SELECT @livraison, @departement, f.fichier_source, f.url, f.sha1, f.taille_octets, f.lignes,
                 DATE '{LIVRAISONS[livraison]["publication"]}', DATE '{stats["date_min"].isoformat()}',
                 DATE '{stats["date_max"].isoformat()}', CURRENT_TIMESTAMP()
          FROM UNNEST([{lignes_fichiers}]) AS f;
          COMMIT TRANSACTION;
        EXCEPTION WHEN ERROR THEN
          ROLLBACK TRANSACTION;
          RAISE;
        END;
    """
    client.query(script, job_config=parametres).result()

    # 4. Contrôle
    requete = f"SELECT COUNT(*) AS n FROM {_table(TABLE_DVF)} WHERE livraison = @livraison AND code_departement = @departement"
    nb = next(iter(client.query(requete, job_config=parametres).result())).n
    if nb != stats["lignes"]:
        raise ValueError(f"{TABLE_DVF} : {nb} lignes pour ({livraison}, {departement}) au lieu de {stats['lignes']}")
    logger.info("Table %s : %d lignes pour (%s, %s)", TABLE_DVF, nb, livraison, departement)

    # 5. Nettoyage (la table de travail reste en cas d'échec, pour analyse)
    client.delete_table(f"{GCP_PROJECT_ID}.{BQ_DATASET}.{TABLE_TRAVAIL}", not_found_ok=True)
    return nb
