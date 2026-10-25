import logging

from google.cloud import bigquery

from pipeline.loyers.config import (
    ATTRIBUTION, BQ_DATASET, COLONNES_REFERENCE, GCP_PROJECT_ID, GCP_SA_KEY_PATH, LICENCE, TABLE_LIVRAISONS,
    TABLE_QUARTIERS, TABLE_QUARTIERS_TRAVAIL, TABLE_REFERENCE, TABLE_REFERENCE_TRAVAIL, URL_EXPORT,
)

logger = logging.getLogger(__name__)

CLUSTER_REFERENCE = ["annee", "id_quartier"]
COLONNES_TABLE_REFERENCE = [cible for _, cible in COLONNES_REFERENCE] + ["meuble"]
SURFACE_MAX_QUARTIER_M2 = 20_000_000  # un quartier de Paris fait moins de 20 km² : garde-fou contre une géométrie inversée


def _client():
    return bigquery.Client.from_service_account_json(str(GCP_SA_KEY_PATH), project=GCP_PROJECT_ID)


def _table(nom):
    return f"`{GCP_PROJECT_ID}.{BQ_DATASET}.{nom}`"


def _litteral(valeur):
    """Texte SQL entre apostrophes (échappées avec un antislash, comme en GoogleSQL)."""
    return "'" + str(valeur).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _charger_parquet(client, chemin, table, attendu, cluster=None):
    """Table de travail recréée à chaque chargement ; le nombre de lignes chargées est contrôlé."""
    config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        clustering_fields=cluster,
    )
    with open(chemin, "rb") as f:
        job = client.load_table_from_file(f, f"{GCP_PROJECT_ID}.{BQ_DATASET}.{table}", job_config=config)
    job.result()
    if job.output_rows != attendu:
        raise ValueError(f"{table} : {job.output_rows} lignes chargées pour {attendu} attendues")
    logger.info("Table de travail %s : %d lignes", table, job.output_rows)


def charger(chemin_reference, chemin_quartiers, resultat, stats):
    """Charge les deux Parquet : les tables de référence et des quartiers sont remplacées en une transaction
    (millésimes et géométries du jeu complet), une ligne de traçabilité est ajoutée à loyers_livraisons.
    resultat : sortie de telechargement.preparer ; stats : sortie de transformation.construire_parquet."""
    client = _client()

    # 1. Tables de travail
    _charger_parquet(client, chemin_reference, TABLE_REFERENCE_TRAVAIL, stats["lignes"], CLUSTER_REFERENCE)
    _charger_parquet(client, chemin_quartiers, TABLE_QUARTIERS_TRAVAIL, stats["quartiers"])

    # 2. Tables cibles, créées au premier chargement seulement
    client.query(
        f"CREATE TABLE IF NOT EXISTS {_table(TABLE_REFERENCE)} CLUSTER BY {', '.join(CLUSTER_REFERENCE)} "
        f"AS SELECT * FROM {_table(TABLE_REFERENCE_TRAVAIL)} WHERE FALSE"
    ).result()
    client.query(f"""
        CREATE TABLE IF NOT EXISTS {_table(TABLE_QUARTIERS)} (
            id_quartier INT64, nom_quartier STRING, code_grand_quartier STRING, id_zone INT64, geometrie GEOGRAPHY
        )
    """).result()
    client.query(f"""
        CREATE TABLE IF NOT EXISTS {_table(TABLE_LIVRAISONS)} (
            url STRING, sha1 STRING, taille_octets INT64, lignes INT64, quartiers INT64, annee_min INT64,
            annee_max INT64, modifie_le TIMESTAMP, traite_le TIMESTAMP, licence STRING, attribution STRING,
            date_chargement TIMESTAMP
        )
    """).result()

    # 3. Remplacement des deux tables et trace du chargement, annulés en bloc au moindre échec
    colonnes = ", ".join(COLONNES_TABLE_REFERENCE)
    script = f"""
        BEGIN
          BEGIN TRANSACTION;
          DELETE FROM {_table(TABLE_REFERENCE)} WHERE TRUE;
          INSERT INTO {_table(TABLE_REFERENCE)} ({colonnes}) SELECT {colonnes} FROM {_table(TABLE_REFERENCE_TRAVAIL)};
          DELETE FROM {_table(TABLE_QUARTIERS)} WHERE TRUE;
          INSERT INTO {_table(TABLE_QUARTIERS)} (id_quartier, nom_quartier, code_grand_quartier, id_zone, geometrie)
          SELECT id_quartier, nom_quartier, code_grand_quartier, id_zone, ST_GEOGFROMGEOJSON(geo_shape, make_valid => TRUE)
          FROM {_table(TABLE_QUARTIERS_TRAVAIL)};
          INSERT INTO {_table(TABLE_LIVRAISONS)} (
              url, sha1, taille_octets, lignes, quartiers, annee_min, annee_max, modifie_le, traite_le, licence,
              attribution, date_chargement
          )
          VALUES (
              {_litteral(URL_EXPORT)}, {_litteral(resultat['sha1'])}, {resultat['taille_octets']}, {stats['lignes']},
              {stats['quartiers']}, {stats['annee_min']}, {stats['annee_max']},
              TIMESTAMP {_litteral(resultat['modifie_le'])}, TIMESTAMP {_litteral(resultat['traite_le'])},
              {_litteral(LICENCE)}, {_litteral(ATTRIBUTION)}, CURRENT_TIMESTAMP()
          );
          COMMIT TRANSACTION;
        EXCEPTION WHEN ERROR THEN
          ROLLBACK TRANSACTION;
          RAISE;
        END;
    """
    client.query(script).result()

    # 4. Contrôle (nombres de lignes et surface des quartiers)
    controle = next(iter(client.query(f"""
        SELECT (SELECT COUNT(*) FROM {_table(TABLE_REFERENCE)}) AS reference,
               (SELECT COUNT(*) FROM {_table(TABLE_QUARTIERS)}) AS quartiers,
               (SELECT MAX(ST_AREA(geometrie)) FROM {_table(TABLE_QUARTIERS)}) AS surface_max,
               (SELECT SUM(ST_AREA(geometrie)) FROM {_table(TABLE_QUARTIERS)}) AS surface_totale
    """).result()))
    if controle.reference != stats["lignes"]:
        raise ValueError(f"{TABLE_REFERENCE} : {controle.reference} lignes au lieu de {stats['lignes']}")
    if controle.quartiers != stats["quartiers"]:
        raise ValueError(f"{TABLE_QUARTIERS} : {controle.quartiers} lignes au lieu de {stats['quartiers']}")
    if controle.surface_max is None or controle.surface_max > SURFACE_MAX_QUARTIER_M2:
        raise ValueError(f"{TABLE_QUARTIERS} : surface maximale {controle.surface_max} m² (géométrie inversée ou invalide ?)")
    logger.info(
        "Tables %s (%d lignes) et %s (%d quartiers, %.1f km² au total)",
        TABLE_REFERENCE, controle.reference, TABLE_QUARTIERS, controle.quartiers, controle.surface_totale / 1e6,
    )

    # 5. Nettoyage (les tables de travail restent en cas d'échec, pour analyse)
    client.delete_table(f"{GCP_PROJECT_ID}.{BQ_DATASET}.{TABLE_REFERENCE_TRAVAIL}", not_found_ok=True)
    client.delete_table(f"{GCP_PROJECT_ID}.{BQ_DATASET}.{TABLE_QUARTIERS_TRAVAIL}", not_found_ok=True)
    return controle.reference
