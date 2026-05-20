"""
Enrichissement Google News — fetch contenu réel via Trafilatura.
UPDATE BigQuery raw_news.content + re-embed ChromaDB sanofi_news.
"""
import logging
from typing import Dict, List, Optional, Tuple

import trafilatura
import voyageai
import chromadb
from chromadb.config import Settings
from google.cloud import bigquery
from google.oauth2 import service_account

from pipeline.config import (
    GCP_PROJECT_ID,
    GCP_SA_KEY_PATH,
    BQ_DATASET_NEWS,
    BQ_TABLE_NEWS,
    CHROMA_HOST,
    CHROMA_PORT,
    CHROMA_USER,
    CHROMA_PASSWORD,
    CHROMA_COLLECTION_NEWS,
    VOYAGE_API_KEY,
    VOYAGE_EMBEDDING_MODEL,
    VOYAGE_EMBEDDING_DIMENSIONS,
)

logger = logging.getLogger(__name__)

VOYAGE_BATCH_SIZE = 128


def _get_bq_client() -> bigquery.Client:
    credentials = service_account.Credentials.from_service_account_file(
        str(GCP_SA_KEY_PATH),
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return bigquery.Client(project=GCP_PROJECT_ID, credentials=credentials)


def _get_chroma_client() -> chromadb.HttpClient:
    return chromadb.HttpClient(
        host=CHROMA_HOST,
        port=CHROMA_PORT,
        settings=Settings(
            chroma_client_auth_provider="chromadb.auth.basic_authn.BasicAuthClientProvider",
            chroma_client_auth_credentials=f"{CHROMA_USER}:{CHROMA_PASSWORD}",
            anonymized_telemetry=False,
        ),
    )


def _fetch_content(url: str) -> Optional[str]:
    """Fetch et extrait le contenu textuel d'une URL via Trafilatura."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        content = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
        return content if content and len(content.strip()) > 50 else None
    except Exception as e:
        logger.warning(f"⚠️  Trafilatura failed for {url}: {e}")
        return None


def _load_news_from_bq(client: bigquery.Client) -> List[Dict]:
    """Charge tous les articles Google News depuis BigQuery."""
    table_ref = f"{GCP_PROJECT_ID}.{BQ_DATASET_NEWS}.{BQ_TABLE_NEWS}"
    query = f"SELECT id, title, content, metadata FROM `{table_ref}`"
    rows = client.query(query).result()
    return [dict(row) for row in rows]


def _update_bq_content(client: bigquery.Client, updates: List[Tuple[str, str]]) -> int:
    """
    UPDATE BigQuery raw_news.content pour les articles enrichis.
    updates: liste de (id, new_content)
    """
    if not updates:
        return 0

    table_ref = f"{GCP_PROJECT_ID}.{BQ_DATASET_NEWS}.{BQ_TABLE_NEWS}"
    updated = 0

    for doc_id, content in updates:
        escaped = content.replace("'", "\\'")
        query = f"""
            UPDATE `{table_ref}`
            SET content = '{escaped}'
            WHERE id = '{doc_id}'
        """
        try:
            client.query(query).result()
            updated += 1
        except Exception as e:
            logger.error(f"❌ BQ UPDATE failed for {doc_id}: {e}")

    return updated


def _re_embed_chroma(docs: List[Dict]) -> int:
    """Re-embed les documents enrichis dans ChromaDB sanofi_news."""
    import json
    chroma_client = _get_chroma_client()
    voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)
    collection = chroma_client.get_or_create_collection(
        name=CHROMA_COLLECTION_NEWS,
        metadata={"hnsw:space": "cosine"},
    )

    total = 0
    for i in range(0, len(docs), VOYAGE_BATCH_SIZE):
        batch = docs[i:i + VOYAGE_BATCH_SIZE]
        ids = [d["id"] for d in batch]
        texts = [d["content"] for d in batch]
        metadatas = []
        for d in batch:
            meta = d.get("metadata", {})
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            metadatas.append({
                "source": "google_news",
                "title": d.get("title", ""),
                **{k: str(v) for k, v in meta.items()
                   if isinstance(v, (str, int, float, bool))},
            })
        try:
            result = voyage_client.embed(
                texts,
                model=VOYAGE_EMBEDDING_MODEL,
                input_type="document",
                output_dimension=VOYAGE_EMBEDDING_DIMENSIONS,
            )
            collection.upsert(
                ids=ids,
                embeddings=result.embeddings,
                documents=texts,
                metadatas=metadatas,
            )
            total += len(batch)
            logger.info(f"✅ ChromaDB re-embed batch {i // VOYAGE_BATCH_SIZE + 1}: {len(batch)} docs")
        except Exception as e:
            logger.error(f"❌ ChromaDB upsert error batch {i}: {e}")

    return total


def run() -> Dict[str, int]:
    """
    Enrichit les articles Google News existants :
    1. Charge les articles depuis BigQuery
    2. Fetch le contenu réel via Trafilatura
    3. UPDATE BigQuery content
    4. Re-embed ChromaDB
    """
    logger.info("🔍 Enrichissement Google News — démarrage")

    bq_client = _get_bq_client()
    articles = _load_news_from_bq(bq_client)
    logger.info(f"📥 {len(articles)} articles chargés depuis BigQuery")

    enriched, skipped = [], []
    for article in articles:
        import json
        meta = article.get("metadata", {})
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        url = meta.get("url", "")
        if not url:
            skipped.append(article["id"])
            continue

        content = _fetch_content(url)
        if not content:
            logger.warning(f"⚠️  Contenu vide — skipped: {article.get('title', '')[:60]}")
            skipped.append(article["id"])
            continue

        enriched.append({**article, "content": content})

    logger.info(f"✅ {len(enriched)} articles enrichis, {len(skipped)} skipped")

    # UPDATE BigQuery
    updates = [(d["id"], d["content"]) for d in enriched]
    nb_updated = _update_bq_content(bq_client, updates)
    logger.info(f"✅ BigQuery — {nb_updated} articles mis à jour")

    # Re-embed ChromaDB
    nb_embedded = _re_embed_chroma(enriched)
    logger.info(f"✅ ChromaDB — {nb_embedded} articles re-embeddés")

    return {"enriched": len(enriched), "skipped": len(skipped), "bq_updated": nb_updated, "chroma_embedded": nb_embedded}