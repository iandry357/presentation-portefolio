"""Recherche du référentiel bailleur (Immobilier) : BM25 + vecteurs mistral-embed, fusionnés par RRF.

L'index (collection ChromaDB referentiel_immobilier : documents, métadonnées, vecteurs) est lu une seule fois puis gardé en
mémoire ; aucun appel à ChromaDB par question. Mesure (realisations/immobilier/scripts/evaluer_recherche.py, 20 questions, sans
filtre de thème) : un attendu dans les 3 premiers pour 14, dans les 5 premiers pour 19, dans les 8 premiers pour 20.
ChromaDB est lu par son API HTTP : le client chromadb du backend (1.x, via crewai) n'est pas celui du serveur (0.5.20).
"""
import asyncio
import logging
import re
import unicodedata

import httpx
import numpy as np
from rank_bm25 import BM25Okapi

from app.core.config import settings
from app.services.embeddings import generate_embedding_mistral

logger = logging.getLogger(__name__)

COLLECTION = "referentiel_immobilier"
CHROMA_COLLECTIONS = "/api/v2/tenants/default_tenant/databases/default_database/collections"
TAILLE_PAGE = 100
NB_CANDIDATS = 50  # profondeur lue dans chaque liste avant la fusion
RRF_K = 60
K_DEFAUT = 6
MOTS_VIDES = {  # sans accents, comme les jetons
    "le", "la", "les", "de", "du", "des", "un", "une", "et", "au", "aux", "en", "ce", "que", "qui", "pour", "par", "sur",
    "dans", "est", "sont", "ou", "il", "je", "mon", "ma", "puis", "dois", "quel", "quelle", "quels", "quelles", "comment",
    "combien", "qu",
}

_index = None
_verrou = asyncio.Lock()


def _tokeniser(texte):
    decompose = unicodedata.normalize("NFD", texte.lower())
    sans_accents = "".join(c for c in decompose if unicodedata.category(c) != "Mn")
    return [m for m in re.findall(r"\w+", sans_accents) if len(m) > 1 and m not in MOTS_VIDES]


async def _lire_collection():
    """Lit tous les chunks de la collection (ids, documents, métadonnées, vecteurs) par pages."""
    base = f"http://{settings.CHROMA_HOST}:{settings.CHROMA_PORT}{CHROMA_COLLECTIONS}"
    ids, documents, metadonnees, vecteurs = [], [], [], []
    async with httpx.AsyncClient(auth=(settings.CHROMA_USER, settings.CHROMA_PASSWORD), timeout=60) as client:
        r = await client.get(f"{base}/{COLLECTION}")
        r.raise_for_status()
        id_collection = r.json()["id"]
        while True:
            r = await client.post(
                f"{base}/{id_collection}/get",
                json={"limit": TAILLE_PAGE, "offset": len(ids), "include": ["documents", "metadatas", "embeddings"]},
            )
            r.raise_for_status()
            page = r.json()
            ids += page["ids"]
            documents += page["documents"]
            metadonnees += page["metadatas"]
            vecteurs += page["embeddings"]
            if len(page["ids"]) < TAILLE_PAGE:
                break
    return ids, documents, metadonnees, vecteurs


async def _charger_index():
    global _index
    if _index is None:
        async with _verrou:
            if _index is None:
                ids, documents, metadonnees, vecteurs = await _lire_collection()
                matrice = np.array(vecteurs, dtype=np.float32)
                _index = {
                    "ids": ids, "documents": documents, "metadonnees": metadonnees,
                    "matrice": matrice / np.linalg.norm(matrice, axis=1, keepdims=True),
                    "bm25": BM25Okapi([_tokeniser(d) for d in documents]),
                }
                logger.info("Référentiel immobilier : %d chunks en mémoire (%d dimensions)", len(ids), matrice.shape[1])
    return _index


def invalider_index():
    """Force la relecture de ChromaDB à la prochaine recherche (après un rechargement du corpus)."""
    global _index
    _index = None


async def rechercher(question: str, k: int = K_DEFAUT) -> list[dict]:
    """Les k meilleurs chunks pour la question, classés par fusion RRF (vecteurs mistral-embed + BM25)."""
    index = await _charger_index()
    vecteur = np.array(await generate_embedding_mistral(question), dtype=np.float32)
    similarites = index["matrice"] @ (vecteur / np.linalg.norm(vecteur))
    rang_vecteurs = [int(i) for i in np.argsort(-similarites, kind="stable")[:NB_CANDIDATS]]
    scores_bm25 = index["bm25"].get_scores(_tokeniser(question))
    rang_bm25 = [int(i) for i in np.argsort(-scores_bm25, kind="stable")[:NB_CANDIDATS]]
    rrf = {}
    for liste in (rang_vecteurs, rang_bm25):
        for rang, i in enumerate(liste, 1):
            rrf[i] = rrf.get(i, 0) + 1 / (RRF_K + rang)
    retenus = sorted(rrf, key=rrf.get, reverse=True)[:k]
    return [
        {"id": index["ids"][i], "document": index["documents"][i], "metadata": index["metadonnees"][i],
         "score": round(rrf[i], 4), "similarite": round(float(similarites[i]), 4)}
        for i in retenus
    ]
