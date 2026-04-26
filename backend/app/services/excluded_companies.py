"""
Gestion de la liste des entreprises exclues de Q11.
Stockée dans GCS : portfolio-emploi-config/excluded_companies.json
Cache TTL 5 minutes pour éviter un appel GCS à chaque requête.
"""

import json
import logging
import os
import time

from google.cloud import storage
from google.oauth2 import service_account
from app.core.config import settings

logger = logging.getLogger(__name__)

_BUCKET = "portfolio-emploi-config"
_BLOB   = "excluded_companies.json"
_TTL    = 300  # 5 minutes

_cache: list[str] = []
_cache_ts: float  = 0.0


# def _client() -> storage.Client:
#     return storage.Client()

def _client() -> storage.Client:
    if not settings.GCP_SERVICE_ACCOUNT_JSON:
        raise RuntimeError("GCP_SERVICE_ACCOUNT_JSON non configuré")
    sa_info = json.loads(settings.GCP_SERVICE_ACCOUNT_JSON)
    credentials = service_account.Credentials.from_service_account_info(
        sa_info,
        scopes=["https://www.googleapis.com/auth/devstorage.read_write"],
    )
    return storage.Client(
        project=settings.BQ_PROJECT_ID,
        credentials=credentials,
    )


def _load_from_gcs() -> list[str]:
    try:
        bucket = _client().bucket(_BUCKET)
        blob   = bucket.blob(_BLOB)
        if not blob.exists():
            logger.warning("[ExcludedCompanies] Fichier GCS introuvable — liste vide")
            return []
        data = json.loads(blob.download_as_text(encoding="utf-8"))
        if not isinstance(data, list):
            logger.error("[ExcludedCompanies] Format inattendu — liste vide")
            return []
        return [str(e).strip() for e in data if str(e).strip()]
    except Exception as e:
        logger.error(f"[ExcludedCompanies] Erreur lecture GCS : {e}", exc_info=True)
        return []


def _save_to_gcs(entreprises: list[str]) -> None:
    try:
        bucket = _client().bucket(_BUCKET)
        blob   = bucket.blob(_BLOB)
        blob.upload_from_string(
            json.dumps(sorted(entreprises), ensure_ascii=False, indent=2),
            content_type="application/json",
        )
        logger.info(f"[ExcludedCompanies] {len(entreprises)} entreprises sauvegardées dans GCS")
    except Exception as e:
        logger.error(f"[ExcludedCompanies] Erreur écriture GCS : {e}", exc_info=True)
        raise


def get_excluded(force_refresh: bool = False) -> list[str]:
    """Retourne la liste avec cache TTL 5 min."""
    global _cache, _cache_ts
    now = time.monotonic()
    if force_refresh or (now - _cache_ts) > _TTL:
        _cache    = _load_from_gcs()
        _cache_ts = now
    return _cache


def add_excluded(nom: str) -> list[str]:
    """Ajoute une entreprise. Idempotent — pas de doublon."""
    entreprises = get_excluded(force_refresh=True)
    nom_clean   = nom.strip()
    if nom_clean not in entreprises:
        entreprises = sorted([*entreprises, nom_clean])
        _save_to_gcs(entreprises)
        _invalidate_cache(entreprises)
    return entreprises


def remove_excluded(nom: str) -> list[str]:
    """Retire une entreprise. Idempotent."""
    entreprises = get_excluded(force_refresh=True)
    nom_clean   = nom.strip()
    if nom_clean in entreprises:
        entreprises = [e for e in entreprises if e != nom_clean]
        _save_to_gcs(entreprises)
        _invalidate_cache(entreprises)
    return entreprises


def _invalidate_cache(updated: list[str]) -> None:
    global _cache, _cache_ts
    _cache    = updated
    _cache_ts = time.monotonic()

def add_excluded_batch(noms: list[str]) -> list[str]:
    """Ajoute plusieurs entreprises en une seule écriture GCS. Idempotent."""
    entreprises = get_excluded(force_refresh=True)
    nouveaux    = [n.strip() for n in noms if n.strip() and n.strip() not in entreprises]
    if nouveaux:
        entreprises = sorted([*entreprises, *nouveaux])
        _save_to_gcs(entreprises)
        _invalidate_cache(entreprises)
    return entreprises