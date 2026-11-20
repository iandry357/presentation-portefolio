"""
Logique RAG Beelix — ChromaDB + LiteLLM.
Collection : beelix_veille (dim 768, paraphrase-multilingual-mpnet-base-v2) : fiches d'offres + actualités.
Embedding via Embedding Service OVH port 8004.
"""
import logging
import os
from typing import Dict, List

import chromadb
import httpx
from chromadb.config import Settings

from app.core.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "beelix_veille"
CONTEXT_MAX_CHARS = 1000   # par document : fiche + début de description

OVH_ML_HOST       = os.getenv("OVH_ML_HOST", "51.68.130.23")
EMBEDDING_PORT    = os.getenv("EMBEDDING_SERVICE_PORT", "8004")
EMBEDDING_URL     = f"http://{OVH_ML_HOST}:{EMBEDDING_PORT}/embed"


# ─────────────────────────────────────────
# Clients
# ─────────────────────────────────────────
def _get_chroma_client() -> chromadb.HttpClient:
    return chromadb.HttpClient(
        host=settings.CHROMA_HOST,
        port=settings.CHROMA_PORT,
        settings=Settings(
            chroma_client_auth_provider="chromadb.auth.basic_authn.BasicAuthClientProvider",
            chroma_client_auth_credentials=f"{settings.CHROMA_USER}:{settings.CHROMA_PASSWORD}",
            anonymized_telemetry=False,
        ),
    )


async def _get_embedding(text: str) -> List[float]:
    """Appelle le Embedding Service OVH pour générer l'embedding."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(EMBEDDING_URL, json={"texts": [text]})
        resp.raise_for_status()
        return resp.json()["embeddings"][0]


# ─────────────────────────────────────────
# Retrieval
# ─────────────────────────────────────────
async def retrieve(question: str, n_results: int) -> List[Dict]:
    """Recherche sémantique dans ChromaDB beelix_veille."""
    query_embedding = await _get_embedding(question)

    chroma_client = _get_chroma_client()
    try:
        collection = chroma_client.get_collection(COLLECTION_NAME)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results * 3,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        logger.error(f"[beelix-rag] ChromaDB error : {e}")
        return []

    docs = []
    for i, doc_id in enumerate(results["ids"][0]):
        meta     = results["metadatas"][0][i]
        distance = results["distances"][0][i]
        score    = round(1 - distance, 4)
        docs.append({
            "id":         doc_id,
            "source":     meta.get("source", "offre"),
            "title":      meta.get("title", ""),
            "content":    results["documents"][0][i],
            "url":        meta.get("url", ""),
            "date":       meta.get("date", ""),
            "date_type":  meta.get("date_type", "publication"),
            "entreprise": meta.get("entreprise"),
            "secteur":    meta.get("secteur"),
            "parent":     meta.get("parent_id", doc_id),
            "score":      score,
        })

    docs.sort(key=lambda x: x["score"], reverse=True)

    # Un seul chunk par document : on garde le mieux classé de chaque parent
    seen, unique = set(), []
    for d in docs:
        if d["parent"] in seen:
            continue
        seen.add(d["parent"])
        unique.append(d)
    return unique[:n_results]


# ─────────────────────────────────────────
# Context builder
# ─────────────────────────────────────────
def _date_label(doc: Dict) -> str:
    if doc.get("date_type") == "collecte":
        prefix = "collectée le" if doc.get("source") == "offre" else "collecté le"
    else:
        prefix = "publiée le" if doc.get("source") == "offre" else "publié le"
    return f"{prefix} {doc['date']}"


def build_context(docs: List[Dict]) -> str:
    parts = []
    for i, doc in enumerate(docs, 1):
        nature = "Offre d'emploi" if doc.get("source") == "offre" else "Actualité Beelix"
        parts.append(
            f"[{i}] {nature} — {doc['title']} ({_date_label(doc)})\n"
            f"{doc['content'][:CONTEXT_MAX_CHARS]}\n"
        )
    return "\n---\n".join(parts)


# ─────────────────────────────────────────
# Generation
# ─────────────────────────────────────────
async def generate(question: str, context: str) -> Dict:
    from app.core.llm_client import generate_with_fallback

    system_prompt = """Tu es un assistant d'aide à la prospection commerciale pour Beelix, cabinet de conseil en transformation digitale (UX, produit, data), qui vise notamment les secteurs Banque/Finance/Assurance, Énergie, Automobile, Médias et Télécoms, Luxe et Retail, et Défense.
Le contexte contient des offres d'emploi récentes publiées en Île-de-France (entreprise, secteur, poste, lieu, date) et quelques actualités sur Beelix. Une offre d'emploi est un signal de besoin chez l'entreprise qui recrute ; une offre publiée par une ESN ou un cabinet de conseil signale un concurrent actif.
Tu réponds en français, de manière précise et structurée, en t'appuyant uniquement sur le contexte fourni. Pour chaque entreprise citée, indique le poste concerné et la date.
Le contexte n'est qu'un échantillon des offres les plus proches de la question, pas la totalité : n'affirme jamais de total ni de classement exhaustif, et signale-le si la question en demande un.
Si le contexte ne contient pas l'information demandée, dis-le clairement.
Cite toujours les sources utilisées en indiquant leur numéro et la date entre parenthèses au format JJ/MM/AAAA, par exemple [1] (publiée le 12/11/2026)."""

    user_prompt = f"""Contexte disponible :
{context}

Question : {question}

Réponds en t'appuyant sur le contexte ci-dessus."""

    return await generate_with_fallback(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=1500,
        temperature=0.2,
    )


# ─────────────────────────────────────────
# Pipeline complet
# ─────────────────────────────────────────
async def rag_pipeline(question: str, n_results: int) -> Dict:
    docs = await retrieve(question, n_results)
    if not docs:
        return {
            "answer":      "Aucun document pertinent trouvé pour répondre à cette question.",
            "sources":     [],
            "model_used":  "none",
            "tokens_used": 0,
        }

    context    = build_context(docs)
    llm_result = await generate(question, context)

    return {
        "answer":  llm_result["response"],
        "sources": [
            {
                "id":         d["id"],
                "source":     d["source"],
                "title":      d["title"],
                "url":        d["url"],
                "date":       _date_label(d),
                "score":      d["score"],
                "entreprise": d["entreprise"],
                "secteur":    d["secteur"],
            }
            for d in docs
        ],
        "model_used":  llm_result["provider_used"],
        "tokens_used": llm_result["tokens_used"],
    }
