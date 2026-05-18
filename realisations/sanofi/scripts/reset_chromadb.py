"""
Script de nettoyage ChromaDB — supprime toutes les collections Sanofi.
Usage: docker-compose run --rm pipeline python scripts/reset_chromadb.py
"""
import chromadb
from chromadb.config import Settings
from pipeline.config import (
    CHROMA_HOST,
    CHROMA_PORT,
    CHROMA_USER,
    CHROMA_PASSWORD,
    CHROMA_COLLECTION_CLINICAL_TRIALS,
    CHROMA_COLLECTION_PUBMED,
    CHROMA_COLLECTION_NEWS,
)

client = chromadb.HttpClient(
    host=CHROMA_HOST,
    port=CHROMA_PORT,
    settings=Settings(
        chroma_client_auth_provider="chromadb.auth.basic_authn.BasicAuthClientProvider",
        chroma_client_auth_credentials=f"{CHROMA_USER}:{CHROMA_PASSWORD}",
        anonymized_telemetry=False,
    ),
)

collections = [
    CHROMA_COLLECTION_CLINICAL_TRIALS,
    CHROMA_COLLECTION_PUBMED,
    CHROMA_COLLECTION_NEWS,
]

for col in collections:
    try:
        client.delete_collection(col)
        print(f"✅ Collection supprimée: {col}")
    except Exception as e:
        print(f"⚠️ Collection introuvable ou erreur [{col}]: {e}")

print("✅ Reset ChromaDB terminé.")