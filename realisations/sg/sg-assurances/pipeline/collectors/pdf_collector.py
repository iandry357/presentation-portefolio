"""
Collecteur PDF — SG Assurances.
Télécharge et extrait le texte brut des PDFs publics SG.
Fallback PyMuPDF → pdfplumber si extraction vide ou erreur.
Le chunking est délégué à pipeline/transformers/chunker.py.
"""
import hashlib
import io
import logging
from typing import Dict, List, Optional

import requests

from pipeline.config import PDF_SOURCES

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SGAssurancesCollector/1.0)"
}


def _download_pdf(url: str) -> Optional[bytes]:
    """Télécharge un PDF depuis une URL publique."""
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT, headers=HEADERS)
        response.raise_for_status()
        if "pdf" not in response.headers.get("Content-Type", "").lower():
            logger.warning(f"⚠️  Content-Type inattendu pour {url}")
        return response.content
    except Exception as e:
        logger.error(f"❌ Téléchargement échoué pour {url}: {e}")
        return None


def _extract_with_pymupdf(pdf_bytes: bytes) -> Optional[str]:
    """Extrait le texte brut via PyMuPDF (fitz)."""
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        for page in doc:
            text = page.get_text("text")
            if text.strip():
                pages.append(text.strip())
        doc.close()
        full_text = "\n\n".join(pages)
        return full_text if len(full_text.strip()) > 50 else None
    except Exception as e:
        logger.warning(f"⚠️  PyMuPDF échoué: {e}")
        return None


def _extract_with_pdfplumber(pdf_bytes: bytes) -> Optional[str]:
    """Extrait le texte brut via pdfplumber (fallback)."""
    try:
        import pdfplumber
        pages = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text and text.strip():
                    pages.append(text.strip())
        full_text = "\n\n".join(pages)
        return full_text if len(full_text.strip()) > 50 else None
    except Exception as e:
        logger.warning(f"⚠️  pdfplumber échoué: {e}")
        return None


def _extract_text(pdf_bytes: bytes, name: str) -> Optional[str]:
    """
    Extrait le texte brut d'un PDF.
    Stratégie : PyMuPDF en premier, pdfplumber en fallback.
    """
    text = _extract_with_pymupdf(pdf_bytes)
    if text:
        logger.info(f"✅ [{name}] extraction PyMuPDF réussie")
        return text

    logger.info(f"🔄 [{name}] PyMuPDF vide — fallback pdfplumber")
    text = _extract_with_pdfplumber(pdf_bytes)
    if text:
        logger.info(f"✅ [{name}] extraction pdfplumber réussie")
        return text

    logger.error(f"❌ [{name}] extraction échouée (PyMuPDF + pdfplumber)")
    return None


def _collect_pdf(pdf_cfg: Dict) -> Optional[Dict]:
    """
    Collecte et extrait le texte brut d'un PDF unique.

    Args:
        pdf_cfg: entrée de PDF_SOURCES (name, url, doc_type)

    Returns:
        Document au format unifié pipeline ou None si échec.
    """
    name = pdf_cfg["name"]
    url = pdf_cfg["url"]
    doc_type = pdf_cfg["doc_type"]

    logger.info(f"🔍 [{name}] — téléchargement PDF")

    pdf_bytes = _download_pdf(url)
    if not pdf_bytes:
        return None

    text = _extract_text(pdf_bytes, name)
    if not text:
        return None

    doc_id = f"sg_pdf_{name}_{hashlib.md5(url.encode()).hexdigest()[:16]}"

    return {
        "id": doc_id,
        "source": "pdf",
        "date": None,
        "title": name.replace("_", " ").title(),
        "content": text,
        "metadata": {
            "url": url,
            "doc_type": doc_type,
            "source_name": "SG Assurances",
            "feed_name": "pdf",
        },
    }


def collect() -> List[Dict]:
    """
    Collecte et extrait le texte brut de tous les PDFs configurés.

    Returns:
        Liste de documents au format unifié pipeline.
        Note : le contenu n'est pas encore chunké — délégué à chunker.py.
    """
    all_docs = []
    for pdf_cfg in PDF_SOURCES:
        doc = _collect_pdf(pdf_cfg)
        if doc:
            all_docs.append(doc)

    logger.info(f"✅ PDF total — {len(all_docs)}/{len(PDF_SOURCES)} documents collectés")
    return all_docs