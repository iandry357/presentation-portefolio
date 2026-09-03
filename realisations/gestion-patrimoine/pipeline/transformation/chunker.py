"""
Chunker — Gestion Patrimoine.
Découpe les articles de loi trop longs en sous-chunks suivant leur structure
juridique interne (I/II/III, 1°/2°, a./b./c.), avec repli par regroupement de
phrases quand aucun marqueur fiable n'est détecté.
Les articles courts (< seuil) sont retournés tels quels, sans découpage.
"""
import logging
import re
from typing import Dict, List

logger = logging.getLogger(__name__)

CHUNK_WORD_THRESHOLD = 500

# Marqueurs reconnus : chiffres romains (I., II., III...), degrés (1°, 2°...),
# lettres suivies d'un point ou d'une parenthèse (a., b., a), b)...)
_MARKER_PATTERN = re.compile(
    r"(?:"
    r"(?P<roman>[IVXLCDM]{1,5})\."
    r"|(?P<degree>\d{1,2})°"
    r"|(?P<letter>[a-h])[\.\)]"
    r")"
)

_BOUNDARY_CHARS = {".", ":", ";"}


def _tokenize(text: str) -> List[str]:
    """Tokenisation simple par mots — pas de dépendance externe."""
    return text.split()


def _find_marker_positions(text: str) -> List[int]:
    """
    Repère les positions de début de segment marquées par un marqueur juridique
    (I/II/III, 1°/2°, a./b./c.), en ne retenant que les marqueurs précédés
    d'une frontière de phrase (., :, ;) ou situés en tout début de texte —
    ce qui évite de couper sur des faux positifs comme "75 %" ou "articles 34".
    """
    positions = []
    for match in _MARKER_PATTERN.finditer(text):
        start = match.start()

        # Caractère non-blanc précédant le marqueur
        j = start - 1
        while j >= 0 and text[j].isspace():
            j -= 1

        is_boundary = j < 0 or text[j] in _BOUNDARY_CHARS
        if is_boundary:
            positions.append(start)

    return positions


def _split_by_markers(text: str) -> List[str]:
    """
    Découpe le texte aux positions de marqueurs juridiques valides.
    Retourne une liste vide si moins de deux marqueurs valides sont trouvés
    (découpage jugé non fiable dans ce cas, on laisse la main au repli phrases).
    """
    positions = _find_marker_positions(text)

    if len(positions) < 2:
        return []

    segments = []
    for i, pos in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(text)
        segment = text[pos:end].strip()
        if segment:
            segments.append(segment)

    return segments


def _split_sentences(text: str) -> List[str]:
    """Découpe un texte en phrases sur la ponctuation forte (., !, ?)."""
    raw = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in raw if s.strip()]


def _split_by_sentences_grouped(text: str, word_threshold: int = CHUNK_WORD_THRESHOLD) -> List[str]:
    """
    Repli utilisé quand aucun marqueur fiable n'est détecté : regroupe les
    phrases consécutives jusqu'à atteindre ~word_threshold mots par chunk.
    Ne coupe jamais une phrase en deux.
    """
    sentences = _split_sentences(text)
    if not sentences:
        return [text]

    chunks = []
    current: List[str] = []
    current_words = 0

    for sentence in sentences:
        sentence_words = len(_tokenize(sentence))
        if current and current_words + sentence_words > word_threshold:
            chunks.append(" ".join(current))
            current = []
            current_words = 0
        current.append(sentence)
        current_words += sentence_words

    if current:
        chunks.append(" ".join(current))

    return chunks


def _split_long_content(text: str, word_threshold: int = CHUNK_WORD_THRESHOLD) -> List[str]:
    """
    Découpe un contenu dépassant le seuil de mots.
    Tente d'abord un découpage par marqueurs juridiques ; si non fiable,
    replie sur un regroupement de phrases à ~word_threshold mots.
    """
    segments = _split_by_markers(text)
    if segments:
        return segments

    return _split_by_sentences_grouped(text, word_threshold)


def chunk_document(doc: Dict, word_threshold: int = CHUNK_WORD_THRESHOLD) -> List[Dict]:
    """
    Découpe un document normalisé en chunks.
    Chaque chunk hérite des métadonnées du document parent.

    Args:
        doc: document au format unifié pipeline (sortie de normalize.py)
        word_threshold: seuil de mots au-delà duquel le découpage est déclenché

    Returns:
        Liste de documents chunkés au format unifié pipeline.
    """
    content = doc.get("content", "")
    if not content or not content.strip():
        logger.warning(f"⚠️  Document vide ignoré : {doc.get('id', 'unknown')}")
        return []

    word_count = len(_tokenize(content))
    if word_count <= word_threshold:
        return [doc]

    segments = _split_long_content(content, word_threshold)

    if len(segments) == 1:
        return [doc]

    chunked_docs = []
    for i, segment in enumerate(segments):
        chunked_doc = {
            **doc,
            "id": f"{doc['id']}_chunk_{i}",
            "content": segment,
            "metadata": {
                **doc.get("metadata", {}),
                "chunk_index": i,
                "chunk_total": len(segments),
                "parent_id": doc["id"],
            },
        }
        chunked_docs.append(chunked_doc)

    logger.info(f"✅ [{doc.get('id', 'unknown')}] — {len(segments)} chunks générés")
    return chunked_docs


def chunk_documents(docs: List[Dict], word_threshold: int = CHUNK_WORD_THRESHOLD) -> List[Dict]:
    """
    Découpe une liste de documents normalisés en chunks.

    Args:
        docs: liste de documents au format unifié pipeline
        word_threshold: seuil de mots au-delà duquel le découpage est déclenché

    Returns:
        Liste complète de documents chunkés.
    """
    all_chunks = []
    for doc in docs:
        chunks = chunk_document(doc, word_threshold)
        all_chunks.extend(chunks)

    logger.info(f"✅ Chunking total — {len(docs)} docs → {len(all_chunks)} chunks")
    return all_chunks