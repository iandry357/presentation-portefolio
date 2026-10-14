import logging
from datetime import datetime, timezone
from typing import Optional

from google.cloud import bigquery

from pipeline import config

logger = logging.getLogger(__name__)

TABLE_CIBLES = f"{config.GCP_PROJECT_ID}.{config.BQ_DATASET}.cibles"


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
