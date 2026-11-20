"""
Orchestrateur principal du pipeline Wavestone.
Collecte (site + Google News + offres BigQuery) → Fiches → Normalisation → Chunking → Validation
→ Chargement BigQuery (articles_bruts, offres_wavestone) + ChromaDB (site, presse, fiches d'offres).
"""
import logging
import sys
from datetime import datetime

from pipeline.collectors import google_news, offres_bigquery, wavestone_site
from pipeline.transformation import fiches
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

SOURCES_ARTICLES = ("google_news", "wavestone_site")   # sources chargées dans articles_bruts


def run():
    """Lance le pipeline complet."""
    start = datetime.utcnow()
    logger.info("=" * 60)
    logger.info("🚀 Pipeline Wavestone — Démarrage")
    logger.info(f"⏰ {start.isoformat()}")
    logger.info("=" * 60)

    # ── 1. Collecte ──────────────────────────────────────────
    logger.info("\n📥 ÉTAPE 1 — Collecte")
    site_docs = wavestone_site.collect()
    news_docs = google_news.collect()
    offres = offres_bigquery.collect()
    logger.info(f"📊 Collecté : {len(site_docs)} pages du site, {len(news_docs)} articles de presse, {len(offres)} offres")

    if not offres:
        logger.warning("⚠️ Aucune offre sur la fenêtre — offres_wavestone et fiches inchangées")

    # ── 2. Fiches ────────────────────────────────────────────
    logger.info("\n🗂️  ÉTAPE 2 — Fiches d'offres")
    fiches_docs = fiches.construire_fiches(offres)

    # ── 3. Normalisation ─────────────────────────────────────
    logger.info("\n🔄 ÉTAPE 3 — Normalisation")
    normalized_docs = normalize_batch(site_docs + news_docs + fiches_docs)

    # ── 4. Chunking ──────────────────────────────────────────
    logger.info("\n✂️  ÉTAPE 4 — Chunking")
    chunked_docs = chunk_documents(normalized_docs)
    logger.info(f"📊 {len(normalized_docs)} docs → {len(chunked_docs)} chunks")

    # ── 5. Validation ────────────────────────────────────────
    logger.info("\n✅ ÉTAPE 5 — Validation qualité")
    valid_docs = validate_batch(chunked_docs)

    if not valid_docs:
        logger.error("❌ Aucun document valide après validation — pipeline arrêté")
        sys.exit(1)

    # ── 6. Chargement BigQuery ───────────────────────────────
    logger.info("\n💾 ÉTAPE 6 — Chargement BigQuery")
    bq_summary = bigquery_loader.load([d for d in valid_docs if d["source"] in SOURCES_ARTICLES])
    for source, count in bq_summary.items():
        logger.info(f"   BigQuery [{source}]: {count} docs")
    nb_offres = bigquery_loader.charger_offres(offres)
    logger.info(f"   BigQuery [offres_wavestone]: {nb_offres} offres")

    # ── 7. Chargement ChromaDB ───────────────────────────────
    logger.info("\n🔍 ÉTAPE 7 — Chargement ChromaDB")
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
