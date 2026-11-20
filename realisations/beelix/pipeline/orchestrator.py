"""
Orchestrateur principal du pipeline Beelix.
Collecte (Google News + offres BigQuery) → Secteurs → Fiches → Normalisation → Chunking → Validation
→ Chargement BigQuery (articles_bruts, offres_signaux) + ChromaDB (actualités, fiches d'offres).
"""
import logging
import sys
from datetime import datetime

from pipeline.collectors import google_news, offres_bigquery
from pipeline.transformation import fiches, secteurs
from pipeline.transformation.normalize import normalize_batch
from pipeline.transformation.chunker import chunk_documents
from pipeline.validators.quality import validate_batch
from pipeline.loaders import bigquery_loader, chroma_loader

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
    logger.info("🚀 Pipeline Beelix — Démarrage")
    logger.info(f"⏰ {start.isoformat()}")
    logger.info("=" * 60)

    # ── 1. Collecte ──────────────────────────────────────────
    logger.info("\n📥 ÉTAPE 1 — Collecte")
    news_docs = google_news.collect()
    offres = offres_bigquery.collect()
    logger.info(f"📊 Collecté : {len(news_docs)} actualités, {len(offres)} offres")

    if not offres:
        logger.error("❌ Aucune offre sur la fenêtre — pipeline arrêté (offres_signaux inchangée)")
        sys.exit(1)

    # ── 2. Secteurs ──────────────────────────────────────────
    logger.info("\n🏷️  ÉTAPE 2 — Secteurs")
    secteurs.enrichir(offres)

    # ── 3. Fiches ────────────────────────────────────────────
    logger.info("\n🗂️  ÉTAPE 3 — Fiches d'offres (secteurs RAG)")
    fiches_docs = fiches.construire_fiches(offres)

    # ── 4. Normalisation ─────────────────────────────────────
    logger.info("\n🔄 ÉTAPE 4 — Normalisation")
    normalized_docs = normalize_batch(news_docs + fiches_docs)

    # ── 5. Chunking ──────────────────────────────────────────
    logger.info("\n✂️  ÉTAPE 5 — Chunking")
    chunked_docs = chunk_documents(normalized_docs)
    logger.info(f"📊 {len(normalized_docs)} docs → {len(chunked_docs)} chunks")

    # ── 6. Validation ────────────────────────────────────────
    logger.info("\n✅ ÉTAPE 6 — Validation qualité")
    valid_docs = validate_batch(chunked_docs)

    if not valid_docs:
        logger.error("❌ Aucun document valide après validation — pipeline arrêté")
        sys.exit(1)

    # ── 7. Chargement BigQuery ───────────────────────────────
    logger.info("\n💾 ÉTAPE 7 — Chargement BigQuery")
    bq_summary = bigquery_loader.load([d for d in valid_docs if d["source"] == "google_news"])
    for source, count in bq_summary.items():
        logger.info(f"   BigQuery [{source}]: {count} docs")
    nb_offres = bigquery_loader.charger_offres(offres)
    logger.info(f"   BigQuery [offres_signaux]: {nb_offres} offres")

    # ── 8. Chargement ChromaDB ───────────────────────────────
    logger.info("\n🔍 ÉTAPE 8 — Chargement ChromaDB")
    chroma_summary = chroma_loader.load(valid_docs)
    for source, count in chroma_summary.items():
        logger.info(f"   ChromaDB [{source}]: {count} docs")

    # ── Résumé ───────────────────────────────────────────────
    elapsed = (datetime.utcnow() - start).total_seconds()
    logger.info("\n" + "=" * 60)
    logger.info("🎯 Pipeline terminé avec succès")
    logger.info(f"⏱️  Durée: {elapsed:.1f}s")
    logger.info(f"📊 Offres: {nb_offres} — documents indexés: {len(valid_docs)}")
    logger.info("=" * 60)


if __name__ == "__main__":
    run()
