"""
Orchestrateur principal du pipeline Sanofi.
Collecte → Normalisation → Validation → Chargement BigQuery + ChromaDB.
"""
import logging
import sys
from datetime import datetime

from pipeline.collectors import clinical_trials, pubmed, google_news
from pipeline.transformers.normalize import normalize_batch
from pipeline.validators.quality import validate_batch
from pipeline.loaders import bigquery_loader, chroma_loader

from pipeline.collectors import press_releases

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def run():
    """Lance le pipeline complet."""
    start = datetime.utcnow()
    logger.info("=" * 60)
    logger.info("🚀 Pipeline Sanofi Intelligence — Démarrage")
    logger.info(f"⏰ {start.isoformat()}")
    logger.info("=" * 60)

    # ── 1. Collecte ──────────────────────────────────────────
    logger.info("\n📥 ÉTAPE 1 — Collecte")

    ct_docs = clinical_trials.collect()
    pm_docs = pubmed.collect()
    gn_docs = google_news.collect()
    pr_docs = press_releases.collect()
    
    raw_docs = ct_docs + pm_docs + gn_docs + pr_docs

    logger.info(f"📊 Total collecté: {len(raw_docs)} documents "
                f"(ClinicalTrials: {len(ct_docs)}, PubMed: {len(pm_docs)}, News: {len(gn_docs)}, PressReleases: {len(pr_docs)})")

    if not raw_docs:
        logger.error("❌ Aucun document collecté — pipeline arrêté")
        sys.exit(1)

    # ── 2. Normalisation ─────────────────────────────────────
    logger.info("\n🔄 ÉTAPE 2 — Normalisation")
    normalized_docs = normalize_batch(raw_docs)

    # ── 3. Validation ────────────────────────────────────────
    logger.info("\n✅ ÉTAPE 3 — Validation qualité")
    valid_docs = validate_batch(normalized_docs)

    if not valid_docs:
        logger.error("❌ Aucun document valide après validation — pipeline arrêté")
        sys.exit(1)

    # ── 4. Chargement BigQuery ───────────────────────────────
    logger.info("\n💾 ÉTAPE 4 — Chargement BigQuery")
    bq_summary = bigquery_loader.load(valid_docs)
    for source, count in bq_summary.items():
        logger.info(f"   BigQuery [{source}]: {count} docs")

    # ── 5. Chargement ChromaDB ───────────────────────────────
    logger.info("\n🔍 ÉTAPE 5 — Chargement ChromaDB")
    chroma_summary = chroma_loader.load(valid_docs)
    for source, count in chroma_summary.items():
        logger.info(f"   ChromaDB [{source}]: {count} docs")

    # ── Résumé ───────────────────────────────────────────────
    elapsed = (datetime.utcnow() - start).total_seconds()
    logger.info("\n" + "=" * 60)
    logger.info("🎯 Pipeline terminé avec succès")
    logger.info(f"⏱️  Durée: {elapsed:.1f}s")
    logger.info(f"📊 Documents traités: {len(valid_docs)}/{len(raw_docs)}")
    logger.info("=" * 60)


if __name__ == "__main__":
    run()