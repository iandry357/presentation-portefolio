import json
import logging

from google.cloud import storage

from pipeline import config

logger = logging.getLogger(__name__)


def lire_exclues() -> list[str]:
    """Lit excluded_companies.json (tableau JSON de noms) dans GCS ; liste vide si le fichier est absent."""
    blob = (
        storage.Client(project=config.GCP_PROJECT_ID)
        .bucket(config.GCS_BUCKET)
        .blob(config.EXCLUDED_BLOB)
    )
    if not blob.exists():
        logger.warning(
            "gs://%s/%s introuvable — liste d'exclusions vide", config.GCS_BUCKET, config.EXCLUDED_BLOB
        )
        return []
    donnees = json.loads(blob.download_as_text(encoding="utf-8"))
    if not isinstance(donnees, list):
        raise ValueError(f"Format inattendu pour {config.EXCLUDED_BLOB} : tableau JSON attendu")
    noms = [str(nom).strip() for nom in donnees if str(nom).strip()]
    logger.info("Entreprises exclues lues dans GCS : %d", len(noms))
    return noms
