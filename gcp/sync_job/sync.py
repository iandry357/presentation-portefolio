"""
Cloud Run Job — Sync France Travail → BigQuery.

Modes :
  BOOTSTRAP_MODE=true  → fenêtre 2 mois (premier lancement)
  BOOTSTRAP_MODE=false → fenêtre jour J uniquement (quotidien)

Variables d'environnement requises :
  FT_CLIENT_ID, FT_CLIENT_SECRET
  BQ_PROJECT_ID, BQ_DATASET, BQ_TABLE
  ROME_CODES        (séparés par virgule)
  REGION            (défaut: 11)
  BOOTSTRAP_MODE    (défaut: false)
"""

import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone

from google.cloud import bigquery
from google.cloud.exceptions import NotFound

from sources.france_travail import fetch_offers, fetch_offers_by_keywords, normalize

from google.cloud import storage as gcs


# ============================================================================
# Logging
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("sync_job")

# ============================================================================
# Config depuis variables d'environnement
# ============================================================================

def _require_env(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if not val:
        logger.error(f"Variable d'environnement manquante : {key}")
        sys.exit(1)
    return val



# Taille des lots ROME envoyés en une seule requête FT
ROME_BATCH_SIZE = 5

# ============================================================================
# Fenêtre temporelle
# ============================================================================

def _build_window() -> tuple[str, str]:
    """
    Retourne (date_min, date_max) au format ISO 8601.
    Bootstrap : 2 derniers mois.
    Quotidien  : jour J uniquement.
    """
    today = date.today()

    if BOOTSTRAP_MODE:
        date_min = today - timedelta(days=60)
        logger.info(f"Mode BOOTSTRAP — fenêtre {date_min} → {today}")
    else:
        date_min = today
        logger.info(f"Mode quotidien — fenêtre {date_min} → {today}")

    return (
        date_min.strftime("%Y-%m-%dT00:00:00Z"),
        today.strftime("%Y-%m-%dT23:59:59Z"),
    )

def _load_rome_config(bq_client) -> tuple[list[str], list[str]]:
    """
    Charge ROME_CODES et MOTS_CLES depuis Cloud Storage.
    Fallback sur variables d'environnement si fichier absent.
    """
    gcs_bucket   = os.environ.get("GCS_BUCKET", "portfolio-emploi-config")
    gcs_rome_file = "rome_codes_direct.json"
    try:
        import json
        gcs_client = gcs.Client()
        bucket = gcs_client.bucket(gcs_bucket)
        blob = bucket.blob(gcs_rome_file)
        content = blob.download_as_text()
        data = json.loads(content)
        codes_valides = {k: v for k, v in data.items() if v.get("metier_OK", True)}
        rome_codes = list(codes_valides.keys())
        mots_cles = list(dict.fromkeys(v["source"] for v in codes_valides.values()))
        logger.info(f"Config chargée depuis Cloud Storage — {len(rome_codes)} codes ROME, {len(mots_cles)} mots-clés")
        return rome_codes, mots_cles
    except Exception as e:
        logger.warning(f"Cloud Storage indisponible — fallback variables d'env : {e}")
        rome_codes = [c.strip() for c in os.environ.get("ROME_CODES", "").split(",") if c.strip()]
        mots_cles  = [m.strip() for m in os.environ.get("MOTS_CLES", "").split(",") if m.strip()]
        return rome_codes, mots_cles

# ============================================================================
# BigQuery — insertion idempotente
# ============================================================================

def _insert_rows(client: bigquery.Client, rows: list[dict]) -> int:
    """
    Insère les lignes dans BigQuery via MERGE sur id_unique.
    Retourne le nombre de lignes effectivement insérées.
    Ignore les lignes déjà présentes.
    """
    if not rows:
        return 0

    # Récupère les id_unique déjà présents pour ce lot
    ids = [r["id_unique"] for r in rows]
    ids_str = ", ".join(f"'{i}'" for i in ids)

    # query = f"""
    #     SELECT id_unique
    #     FROM `{BQ_TABLE_REF}`
    #     WHERE id_unique IN ({ids_str})
    # """

    table_ref = f"{BQ_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}"
    query = f"""
        SELECT id_unique
        FROM `{table_ref}`
        WHERE id_unique IN ({ids_str})
    """
    logger.info(f"DEBUG _insert_rows — table_ref='{table_ref}' ids_count={len(ids)}")
    try:
        existing = {row.id_unique for row in client.query(query).result()}
    except NotFound:
        existing = set()

    new_rows = [r for r in rows if r["id_unique"] not in existing]

    if not new_rows:
        logger.info(f"Lot ignoré — {len(rows)} offre(s) déjà présente(s)")
        return 0

    errors = client.insert_rows_json(table_ref, new_rows)
    if errors:
        logger.error(f"Erreurs insertion BigQuery : {errors}")
        return 0

    logger.info(f"{len(new_rows)} offre(s) insérée(s) ({len(rows) - len(new_rows)} doublon(s) ignoré(s))")
    return len(new_rows)

# ============================================================================
# Main
# ============================================================================

def main() -> None:
    import os
    all_env = {k: v[:4] + "***" if "SECRET" in k or "KEY" in k else v 
               for k, v in os.environ.items()}
    logger.info(f"ENV disponibles : {list(all_env.keys())}")

    global FT_CLIENT_ID, FT_CLIENT_SECRET, BQ_PROJECT_ID, BQ_DATASET, BQ_TABLE
    global ROME_CODES, MOTS_CLES, REGION, BOOTSTRAP_MODE, BQ_TABLE_REF

    FT_CLIENT_ID     = _require_env("FT_CLIENT_ID")
    FT_CLIENT_SECRET = _require_env("FT_CLIENT_SECRET")
    BQ_PROJECT_ID    = _require_env("BQ_PROJECT_ID")
    BQ_DATASET       = _require_env("BQ_DATASET")
    BQ_TABLE         = _require_env("BQ_TABLE")

    ROME_CODES, MOTS_CLES = _load_rome_config(None)
    if not ROME_CODES:
        logger.error("Aucun code ROME disponible — arrêt")
        sys.exit(1)
    REGION         = os.environ.get("REGION", "11").strip()
    BOOTSTRAP_MODE = os.environ.get("BOOTSTRAP_MODE", "false").strip().lower() == "true"
    BQ_TABLE_REF   = f"{BQ_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}"
    logger.info("=" * 60)
    logger.info("Sync France Travail → BigQuery — démarrage")
    logger.info(f"  Codes ROME    : {ROME_CODES}")
    logger.info(f"  Région        : {REGION}")
    logger.info(f"  Bootstrap     : {BOOTSTRAP_MODE}")
    logger.info(f"  Table cible   : {BQ_TABLE_REF}")
    logger.info("=" * 60)


    date_min, date_max = _build_window()
    import json
    from google.oauth2 import service_account

    sa_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if sa_path:
        # Local — fichier JSON explicite
        import json
        from google.oauth2 import service_account
        with open(sa_path) as f:
            sa_info = json.load(f)
        credentials = service_account.Credentials.from_service_account_info(
            sa_info,
            scopes=["https://www.googleapis.com/auth/bigquery"],
        )
        bq_client = bigquery.Client(project=BQ_PROJECT_ID, credentials=credentials)
    else:
        # Cloud Run — credentials automatiques via Service Account
        bq_client = bigquery.Client(project=BQ_PROJECT_ID)

    logger.info(f"DEBUG client — project='{bq_client.project}'")
    # from google.oauth2 import service_account
    # credentials = service_account.Credentials.from_service_account_file(
    #     os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    # )
    # bq_client = bigquery.Client(
    #     project=BQ_PROJECT_ID,
    #     credentials=credentials,
    # )
    # bq_client = bigquery.Client(project=BQ_PROJECT_ID)

    total_fetched_rome  = 0
    total_fetched_kw    = 0
    total_inserted      = 0
    total_skipped       = 0

    # Filtre titres non pertinents
    _EXCLUDE_KEYWORDS = {"alternan", "apprenti", "stag"}

    def _is_excluded(titre: str) -> bool:
        t = titre.lower()
        return any(kw in t for kw in _EXCLUDE_KEYWORDS)

    # Collecte globale — déduplication sur id_source
    all_offers: dict[str, dict] = {}

    # ── Bras 1 — ROME ──────────────────────────────────────────
    logger.info("── Bras 1 — Collecte par codes ROME ──")
    for i in range(0, len(ROME_CODES), ROME_BATCH_SIZE):
        batch_codes = ROME_CODES[i:i + ROME_BATCH_SIZE]
        logger.info(f"Lot ROME : {batch_codes}")
        try:
            raw_offers = fetch_offers(
                client_id     = FT_CLIENT_ID,
                client_secret = FT_CLIENT_SECRET,
                rome_codes    = batch_codes,
                region        = REGION,
                date_min      = date_min,
                date_max      = date_max,
                range_start   = 0,
                range_end     = 99,
            )
        except Exception as e:
            logger.error(f"Erreur collecte ROME {batch_codes} : {e}")
            continue

        for offer in raw_offers:
            titre = offer.get("intitule", "")
            if _is_excluded(titre):
                total_skipped += 1
                continue
            offer["_source_branch"] = "rome"
            all_offers[offer["id"]] = offer
            total_fetched_rome += 1

    logger.info(f"Bras ROME — {total_fetched_rome} offre(s) retenue(s)")

    # ── Bras 2 — Mots-clés ─────────────────────────────────────
    if MOTS_CLES:
        logger.info("── Bras 2 — Collecte par mots-clés ──")
        for keyword in MOTS_CLES:
            try:
                raw_offers = fetch_offers_by_keywords(
                    client_id     = FT_CLIENT_ID,
                    client_secret = FT_CLIENT_SECRET,
                    keywords      = keyword,
                    region        = REGION,
                    date_min      = date_min,
                    date_max      = date_max,
                    range_start   = 0,
                    range_end     = 99,
                )
            except Exception as e:
                logger.error(f"Erreur collecte motsCles '{keyword}' : {e}")
                continue

            for offer in raw_offers:
                titre = offer.get("intitule", "")
                if _is_excluded(titre):
                    total_skipped += 1
                    continue
                if offer["id"] not in all_offers:
                    offer["_source_branch"] = "mots_cles"
                    all_offers[offer["id"]] = offer
                    total_fetched_kw += 1

        logger.info(f"Bras mots-clés — {total_fetched_kw} offre(s) nouvelles retenue(s)")
    else:
        logger.info("── Bras 2 — ignoré (MOTS_CLES vide) ──")

    # ── Normalisation + insertion BigQuery ─────────────────────
    logger.info(f"Total avant insertion : {len(all_offers)} offre(s) dédupliquées")

    normalized = []
    for offer in all_offers.values():
        row = normalize(offer)
        if row:
            normalized.append(row)
        else:
            total_skipped += 1

    inserted = _insert_rows(bq_client, normalized)
    total_inserted += inserted

    # ── Rapport final ───────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("Sync terminée")
    logger.info(f"  Bras ROME      : {total_fetched_rome} offre(s)")
    logger.info(f"  Bras mots-clés : {total_fetched_kw} offre(s) nouvelles")
    logger.info(f"  Total collecté : {len(all_offers)} offre(s) dédupliquées")
    logger.info(f"  Insérées BQ    : {total_inserted}")
    logger.info(f"  Filtrées       : {total_skipped} (alternance/stage/invalides)")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()