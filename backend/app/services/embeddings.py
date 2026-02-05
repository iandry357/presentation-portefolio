import httpx
from typing import List
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


async def vectorize_query(query: str) -> List[float]:
    """
    Génère embedding pour une query via Voyage API.
    
    Args:
        query: Texte à vectoriser
        
    Returns:
        Liste de floats (embedding vector)
    """
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