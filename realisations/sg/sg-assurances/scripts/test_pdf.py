"""
Test isolation — collecte et extraction PDF SG Assurances.
Valide le téléchargement, l'extraction texte et le chunking.
Lance via : docker-compose run --rm pipeline python scripts/test_pdf.py
"""
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def test_collect():
    logger.info("=" * 60)
    logger.info("TEST 1 — Collecte PDF")
    logger.info("=" * 60)

    from pipeline.collectors.pdf_collector import collect
    
    docs = collect()

    logger.info(f"\n📊 Résultat : {len(docs)} documents collectés\n")
    for doc in docs:
        content_len = len(doc.get("content", ""))
        logger.info(f"  ✅ [{doc['metadata'].get('doc_type', doc['metadata'].get('feed_name', ''))}] {doc['title']}")
        logger.info(f"     id       : {doc['id']}")
        logger.info(f"     contenu  : {content_len} caractères")
        logger.info(f"     url      : {doc['metadata']['url'][:80]}...")
        logger.info("")

    return docs


def test_chunk(docs):
    logger.info("=" * 60)
    logger.info("TEST 2 — Chunking")
    logger.info("=" * 60)

    from pipeline.transformation.chunker import chunk_documents
    chunks = chunk_documents(docs)

    logger.info(f"\n📊 Résultat : {len(docs)} docs → {len(chunks)} chunks\n")
    for doc in docs:
        doc_chunks = [c for c in chunks if c["metadata"].get("parent_id") == doc["id"] or c["id"] == doc["id"]]
        logger.info(f"  📄 {doc['title']} → {len(doc_chunks)} chunk(s)")

    logger.info("")
    logger.info("Aperçu premier chunk du premier document :")
    if chunks:
        first = chunks[0]
        logger.info(f"  id      : {first['id']}")
        logger.info(f"  contenu : {first['content'][:200]}...")

    return chunks


def test_normalize(docs):
    logger.info("=" * 60)
    logger.info("TEST 3 — Normalisation")
    logger.info("=" * 60)

    from pipeline.transformation.normalize import normalize_batch

    normalized = normalize_batch(docs)

    logger.info(f"\n📊 Résultat : {len(normalized)} docs normalisés\n")
    for doc in normalized:
        logger.info(f"  ✅ {doc['title']} — date: {doc['date']}")

    return normalized


if __name__ == "__main__":
    try:
        docs = test_collect()
        if not docs:
            logger.error("❌ Aucun document collecté — arrêt des tests")
            sys.exit(1)

        normalized = test_normalize(docs)
        chunks = test_chunk(normalized)

        logger.info("=" * 60)
        logger.info(f"✅ TOUS LES TESTS OK — {len(chunks)} chunks prêts pour ChromaDB")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ Erreur inattendue : {e}", exc_info=True)
        sys.exit(1)