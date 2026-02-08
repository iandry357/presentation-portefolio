import httpx
from typing import List
from app.core.config import settings
import logging
from litellm import embedding

logger = logging.getLogger(__name__)

async def generate_embedding_mistral(query: str, model: str = "mistral-embed"):
    """
    Génère un embedding via Mistral et LiteLLM, avec une interface asynchrone compatible httpx.
    Args:
        query (str): Texte à transformer en vecteur.
        model (str): Modèle Mistral (ex: "mistral/mistral-embed").
    Returns:
        list[float]: Vecteur d'embedding (1024 dimensions).
    """
    # try:
    #     # Utilisation de LiteLLM pour appeler Mistral (abstraction de l'API HTTP)
    #     response = await embedding(
    #         model=model,
    #         input=[query],
    #         # Configuration pour forcer l'usage de httpx (optionnel, LiteLLM gère le client HTTP)
    #         custom_llm_provider="mistral",
    #         async_mode=True  # Active le mode asynchrone
    #     )
    #     # Extraction du vecteur depuis la réponse LiteLLM
    #     # embedding_vector = response.data[0]['embedding']
    #     embeddings = [d["embedding"] for d in response.data][0] 
    #     logger.info(f"✅ Embedding generated: {len(embedding_vector)} dimensions")
    #     return embedding_vector
    url = "https://api.mistral.ai/v1/embeddings"  # URL officielle de l'API Mistral
    headers = {
        "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",  # Remplace par ta clé
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "input": [query]  # Mistral attend une liste de textes
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            embedding = data["data"][0]["embedding"]  # Structure de la réponse Mistral
            logger.info(f"✅ Embedding generated: {len(embedding)} dimensions")
            return embedding
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ Erreur HTTP: {e.response.status_code} - {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"❌ Erreur lors de la génération de l'embedding: {e}")
        raise  # Ou retourne un vecteur par défaut en fallback


async def vectorize_query(query: str, modelEmbeddings: str) -> List[float]:
    """
    Génère embedding pour une query via Voyage API.
    
    Args:
        query: Texte à vectoriser
        
    Returns:
        Liste de floats (embedding vector)
    """
    if modelEmbeddings == "voyage":
        url = "https://api.voyageai.com/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {settings.VOYAGE_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "input": [query],
            "model": settings.EMBEDDING_MODEL
        }
    

    
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                embedding = data["data"][0]["embedding"]
                logger.info(f"✅ Embedding generated: {len(embedding)} dimensions")
                return embedding
        except Exception as e:
            logger.error(f"❌ Voyage API error: {e}")
            raise

    if modelEmbeddings == "mistral":
        await generate_embedding_mistral(query)