"""
Orchestrateur d'enrichissement — indépendant du pipeline de collecte.
Enrichit le contenu des sources existantes via Trafilatura.
"""
import logging
import sys
from datetime import datetime

from pipeline.enrichers import google_news_enricher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def run():
    start = datetime.utcnow()
    logger.info("=" * 60)
    logger.info("🚀 Pipeline Enrichissement Sanofi — Démarrage")
    logger.info(f"⏰ {start.isoformat()}")
    logger.info("=" * 60)

    # ── Google News ──────────────────────────────────────────
    logger.info("\n📰 Enrichissement Google News")
    gn_summary = google_news_enricher.run()
    logger.info(f"   Enrichis   : {gn_summary['enriched']}")
    logger.info(f"   Skipped    : {gn_summary['skipped']}")
    logger.info(f"   BQ updated : {gn_summary['bq_updated']}")
    logger.info(f"   Chroma     : {gn_summary['chroma_embedded']}")

    elapsed = (datetime.utcnow() - start).total_seconds()
    logger.info("\n" + "=" * 60)
    logger.info("🎯 Enrichissement terminé")
    logger.info(f"⏱️  Durée: {elapsed:.1f}s")
    logger.info("=" * 60)


if __name__ == "__main__":
    run()