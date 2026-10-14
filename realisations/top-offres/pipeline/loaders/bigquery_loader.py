import logging
from datetime import datetime, timezone
from typing import Optional

from google.cloud import bigquery

from pipeline import config

logger = logging.getLogger(__name__)

TABLE_CIBLES = f"{config.GCP_PROJECT_ID}.{config.BQ_DATASET}.cibles"
TABLE_EXCLUES = f"{config.GCP_PROJECT_ID}.{config.BQ_DATASET}.entreprises_exclues"
TABLE_ENTREPRISES_REF = f"{config.GCP_PROJECT_ID}.{config.BQ_DATASET}.entreprises_ref"
TABLE_INTERMEDIAIRES = f"{config.GCP_PROJECT_ID}.{config.BQ_DATASET}.intermediaires_connus"  # seed dbt


def _client() -> bigquery.Client:
    """Client BigQuery : identifiants lus via GOOGLE_APPLICATION_CREDENTIALS."""
    return bigquery.Client(project=config.GCP_PROJECT_ID, location=config.BQ_LOCATION)


def _param_version(version_cibles: str) -> bigquery.QueryJobConfig:
    return bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("v", "STRING", version_cibles)]
    )


def _lignes_cibles(version: dict, statut: str, valide_le: Optional[str]) -> list[dict]:
    return [
        {
            "version_cibles": version["version_cibles"],
            "cible_id": c["cible_id"],
            "intitule": c["intitule"],
            "niveau": c["niveau"],
            "justification": c["justification"],
            "variantes_titres": c["variantes_titres"],
            "description": c["description"],
            "modele": version["modele"],
            "statut": statut,
            "cree_le": version["cree_le"],
            "valide_le": valide_le,
        }
        for c in version["cibles"]
    ]


def _charger_cibles(client: bigquery.Client, lignes: list[dict]) -> None:
    """Job de chargement (pas de streaming : les lignes restent modifiables par DML)."""
    job_config = bigquery.LoadJobConfig(write_disposition=bigquery.WriteDisposition.WRITE_APPEND)
    client.load_table_from_json(lignes, TABLE_CIBLES, job_config=job_config).result()


def ecrire_cibles_proposees(version: dict) -> int:
    lignes = _lignes_cibles(version, statut="proposee", valide_le=None)
    _charger_cibles(_client(), lignes)
    logger.info("BigQuery : %d cibles écrites (proposee) dans %s", len(lignes), TABLE_CIBLES)
    return len(lignes)


def statut_version(version_cibles: str) -> Optional[str]:
    """Statut de la version en base, ou None si elle n'existe pas."""
    requete = f"SELECT statut FROM `{TABLE_CIBLES}` WHERE version_cibles = @v GROUP BY statut"
    lignes = list(_client().query(requete, job_config=_param_version(version_cibles)).result())
    return lignes[0].statut if lignes else None


def supprimer_lignes_proposees(version_cibles: str) -> None:
    requete = f"DELETE FROM `{TABLE_CIBLES}` WHERE version_cibles = @v AND statut = 'proposee'"
    _client().query(requete, job_config=_param_version(version_cibles)).result()


def charger_cibles_validees(export: dict) -> int:
    valide_le = datetime.now(timezone.utc).isoformat()
    lignes = _lignes_cibles(export, statut="validee", valide_le=valide_le)
    _charger_cibles(_client(), lignes)
    logger.info("BigQuery : %d cibles chargées (validee)", len(lignes))
    return len(lignes)


def archiver_autres_versions(version_cibles: str) -> None:
    """Une seule version validée active : les autres validées passent à archivee."""
    requete = (
        f"UPDATE `{TABLE_CIBLES}` SET statut = 'archivee' "
        "WHERE statut = 'validee' AND version_cibles != @v"
    )
    _client().query(requete, job_config=_param_version(version_cibles)).result()


def remplacer_exclues(lignes: list[dict]) -> None:
    """Remplace le contenu de entreprises_exclues en conservant la table (et son schéma Terraform)."""
    client = _client()
    if not lignes:
        client.query(f"TRUNCATE TABLE `{TABLE_EXCLUES}`").result()
        return
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        schema=client.get_table(TABLE_EXCLUES).schema,
    )
    client.load_table_from_json(lignes, TABLE_EXCLUES, job_config=job_config).result()
    logger.info("BigQuery : %d entreprises exclues chargées dans %s", len(lignes), TABLE_EXCLUES)


def lire_cles_en_cache(cles: list[str], jours: int) -> set[str]:
    """Clés de entreprises_ref dont la mise à jour date de moins de `jours` jours."""
    if not cles:
        return set()
    requete = (
        f"SELECT nom_normalise FROM `{TABLE_ENTREPRISES_REF}` "
        "WHERE nom_normalise IN UNNEST(@cles) "
        "AND maj_le >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @jours DAY)"
    )
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter("cles", "STRING", cles),
            bigquery.ScalarQueryParameter("jours", "INT64", jours),
        ]
    )
    return {ligne.nom_normalise for ligne in _client().query(requete, job_config=job_config).result()}


def lire_intermediaires() -> set[str]:
    """Noms normalisés du seed dbt intermediaires_connus."""
    requete = f"SELECT nom_normalise FROM `{TABLE_INTERMEDIAIRES}`"
    return {ligne.nom_normalise for ligne in _client().query(requete).result()}


def ecrire_entreprises_ref(lignes: list[dict]) -> int:
    """Remplace les lignes des clés concernées (suppression puis chargement)."""
    if not lignes:
        return 0
    client = _client()
    cles = [ligne["nom_normalise"] for ligne in lignes]
    suppression = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ArrayQueryParameter("cles", "STRING", cles)]
    )
    client.query(
        f"DELETE FROM `{TABLE_ENTREPRISES_REF}` WHERE nom_normalise IN UNNEST(@cles)",
        job_config=suppression,
    ).result()
    job_config = bigquery.LoadJobConfig(write_disposition=bigquery.WriteDisposition.WRITE_APPEND)
    client.load_table_from_json(lignes, TABLE_ENTREPRISES_REF, job_config=job_config).result()
    logger.info("BigQuery : %d entreprises écrites dans %s", len(lignes), TABLE_ENTREPRISES_REF)
    return len(lignes)


TABLE_STAGING = f"{config.GCP_PROJECT_ID}.{config.BQ_DATASET}.offres_scores_staging"


def lire_cibles_validees() -> list[dict]:
    """Cibles de la version validée la plus récente (une seule version active)."""
    requete = f"""
        SELECT version_cibles, cible_id, intitule, niveau, description
        FROM `{TABLE_CIBLES}`
        WHERE statut = 'validee'
          AND version_cibles = (
              SELECT version_cibles FROM `{TABLE_CIBLES}`
              WHERE statut = 'validee' ORDER BY valide_le DESC LIMIT 1
          )
        ORDER BY cible_id
    """
    return [dict(ligne.items()) for ligne in _client().query(requete).result()]


def lire_entreprises_ref(cles: list[str]) -> dict[str, dict]:
    """Lignes de entreprises_ref pour les clés demandées, indexées par nom_normalise."""
    if not cles:
        return {}
    requete = (
        "SELECT nom_normalise, type_annonceur, naf_code, naf_libelle "
        f"FROM `{TABLE_ENTREPRISES_REF}` WHERE nom_normalise IN UNNEST(@cles)"
    )
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ArrayQueryParameter("cles", "STRING", cles)]
    )
    return {
        ligne.nom_normalise: dict(ligne.items())
        for ligne in _client().query(requete, job_config=job_config).result()
    }


def remplacer_staging(lignes: list[dict]) -> None:
    """Remplace le contenu de offres_scores_staging (vidé à chaque run) en conservant la table Terraform."""
    client = _client()
    if not lignes:
        client.query(f"TRUNCATE TABLE `{TABLE_STAGING}`").result()
        return
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        schema=client.get_table(TABLE_STAGING).schema,
    )
    client.load_table_from_json(lignes, TABLE_STAGING, job_config=job_config).result()
    logger.info("BigQuery : %d lignes chargées dans %s", len(lignes), TABLE_STAGING)
