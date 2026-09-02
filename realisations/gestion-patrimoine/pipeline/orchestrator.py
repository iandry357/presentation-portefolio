"""
Orchestrateur principal du pipeline gestion-patrimoine.
Collecte (Légifrance) → Normalisation → Chunking → Validation →
Chargement BigQuery + ChromaDB.

Checkpoints disque (raw_articles.json, chunks.json) pour permettre une
reprise sans re-frapper l'API PISTE — coûteuse en quota.
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime

from pipeline.collectors import legifrance_collector
from pipeline.transformation.normalize import normalize_batch
from pipeline.transformation.chunker import chunk_documents
from pipeline.validators.quality import validate_batch
from pipeline.loaders import bigquery_loader, chroma_loader
from pipeline.config import RAW_ARTICLES_PATH, CHUNKS_PATH

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _collect(force: bool) -> list:
    """Étape 1 — collecte Légifrance, avec checkpoint disque."""
    if not force and os.path.exists(RAW_ARTICLES_PATH):
        logger.info(f"⏭️  Checkpoint trouvé — chargement depuis {RAW_ARTICLES_PATH}")
        return _load_json(RAW_ARTICLES_PATH)

    raw_docs = legifrance_collector.collect()
    _save_json(RAW_ARTICLES_PATH, raw_docs)
    logger.info(f"💾 Checkpoint écrit — {RAW_ARTICLES_PATH}")
    return raw_docs


def _normalize_and_chunk(raw_docs: list, force: bool) -> list:
    """Étape 2 — normalisation + chunking, avec checkpoint disque."""
    if not force and os.path.exists(CHUNKS_PATH):
        logger.info(f"⏭️  Checkpoint trouvé — chargement depuis {CHUNKS_PATH}")
        return _load_json(CHUNKS_PATH)

    normalized_docs = normalize_batch(raw_docs)
    chunked_docs = chunk_documents(normalized_docs)
    _save_json(CHUNKS_PATH, chunked_docs)
    logger.info(f"💾 Checkpoint écrit — {CHUNKS_PATH}")
    return chunked_docs


def run(force_collect: bool = False, force_chunk: bool = False):
    """Lance le pipeline complet."""
    start = datetime.utcnow()
    logger.info("=" * 60)
    logger.info("🚀 Pipeline Gestion Patrimoine — Démarrage")
    logger.info(f"⏰ {start.isoformat()}")
    logger.info("=" * 60)

    # ── 1. Collecte ──────────────────────────────────────────
    logger.info("\n📥 ÉTAPE 1 — Collecte Légifrance")
    raw_docs = _collect(force_collect)
    logger.info(f"📊 Total collecté: {len(raw_docs)} articles")

    if not raw_docs:
        logger.error("❌ Aucun article collecté — pipeline arrêté")
        sys.exit(1)

    # ── 2. Normalisation + Chunking ──────────────────────────
    logger.info("\n✂️  ÉTAPE 2 — Normalisation + Chunking")
    # Si la collecte a été refaite (force_collect), le checkpoint chunks.json
    # est nécessairement périmé : on force aussi son recalcul, même sans
    # --force-chunk explicite, pour ne jamais charger des chunks désynchronisés
    # des articles bruts qu'on vient de recollecter.
    chunked_docs = _normalize_and_chunk(raw_docs, force_chunk or force_collect)
    logger.info(f"📊 {len(raw_docs)} articles → {len(chunked_docs)} chunks")

    # ── 3. Validation ────────────────────────────────────────
    logger.info("\n✅ ÉTAPE 3 — Validation qualité")
    valid_docs = validate_batch(chunked_docs)

    if not valid_docs:
        logger.error("❌ Aucun chunk valide après validation — pipeline arrêté")
        sys.exit(1)

    # ── 4. Chargement BigQuery ───────────────────────────────
    logger.info("\n💾 ÉTAPE 4 — Chargement BigQuery")
    bq_summary = bigquery_loader.load(valid_docs)
    for table, count in bq_summary.items():
        logger.info(f"   BigQuery [{table}]: {count} chunks")

    # ── 5. Chargement ChromaDB ───────────────────────────────
    logger.info("\n🔍 ÉTAPE 5 — Chargement ChromaDB")
    chroma_summary = chroma_loader.load(valid_docs)
    for collection, count in chroma_summary.items():
        logger.info(f"   ChromaDB [{collection}]: {count} chunks")

    # ── Résumé ───────────────────────────────────────────────
    elapsed = (datetime.utcnow() - start).total_seconds()
    logger.info("\n" + "=" * 60)
    logger.info("🎯 Pipeline terminé avec succès")
    logger.info(f"⏱️  Durée: {elapsed:.1f}s")
    logger.info(f"📊 Chunks traités: {len(valid_docs)}/{len(chunked_docs)}")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline gestion-patrimoine")
    parser.add_argument(
        "--force-collect", action="store_true",
        help="Ignore le checkpoint raw_articles.json et recollecte via l'API PISTE",
    )
    parser.add_argument(
        "--force-chunk", action="store_true",
        help="Ignore le checkpoint chunks.json et recalcule normalisation + chunking",
    )
    args = parser.parse_args()

    run(force_collect=args.force_collect, force_chunk=args.force_chunk)