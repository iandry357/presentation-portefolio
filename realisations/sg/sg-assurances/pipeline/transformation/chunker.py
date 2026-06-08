"""
Chunker — SG Assurances.
Découpe les textes longs en chunks de taille fixe avec overlap.
Les textes courts (< chunk_size) sont retournés tels quels sans découpage.
"""
import logging
from typing import Dict, List

from pipeline.config import PIPELINE_BATCH_SIZE

logger = logging.getLogger(__name__)

CHUNK_SIZE = 512
CHUNK_OVERLAP = 50


def _tokenize(text: str) -> List[str]:
    """Tokenisation simple par mots — pas de dépendance externe."""
    return text.split()


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Découpe un texte en chunks de taille fixe avec overlap.

    Args:
        text: texte brut à découper
        chunk_size: nombre de tokens par chunk
        overlap: nombre de tokens de recouvrement entre chunks

    Returns:
        Liste de chunks textuels.
    """
    tokens = _tokenize(text)

    if len(tokens) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(tokens):
        end = start + chunk_size
        chunk_tokens = tokens[start:end]
        chunks.append(" ".join(chunk_tokens))
        start += chunk_size - overlap

    return chunks


def chunk_document(doc: Dict, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[Dict]:
    """
    Découpe un document en chunks.
    Chaque chunk hérite des métadonnées du document parent.

    Args:
        doc: document au format unifié pipeline
        chunk_size: nombre de tokens par chunk
        overlap: nombre de tokens de recouvrement

    Returns:
        Liste de documents chunkés au format unifié pipeline.
    """
    content = doc.get("content", "")
    if not content or not content.strip():
        logger.warning(f"⚠️  Document vide ignoré : {doc.get('id', 'unknown')}")
        return []

    chunks = _chunk_text(content, chunk_size, overlap)

    if len(chunks) == 1:
        return [doc]

    chunked_docs = []
    for i, chunk in enumerate(chunks):
        chunked_doc = {
            **doc,
            "id": f"{doc['id']}_chunk_{i}",
            "content": chunk,
            "metadata": {
                **doc.get("metadata", {}),
                "chunk_index": i,
                "chunk_total": len(chunks),
                "parent_id": doc["id"],
            },
        }
        chunked_docs.append(chunked_doc)

    logger.info(f"✅ [{doc.get('id', 'unknown')}] — {len(chunks)} chunks générés")
    return chunked_docs


def chunk_documents(docs: List[Dict], chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[Dict]:
    """
    Découpe une liste de documents en chunks.

    Args:
        docs: liste de documents au format unifié pipeline
        chunk_size: nombre de tokens par chunk
        overlap: nombre de tokens de recouvrement

    Returns:
        Liste complète de documents chunkés.
    """
    all_chunks = []
    for doc in docs:
        chunks = chunk_document(doc, chunk_size, overlap)
        all_chunks.extend(chunks)

    logger.info(f"✅ Chunking total — {len(docs)} docs → {len(all_chunks)} chunks")
    return all_chunks