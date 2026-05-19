"""
Collecteur PubMed API (esearch + efetch).
Récupère les publications R&D Sanofi 2024-2026.
"""
import logging
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict

from pipeline.config import (
    PUBMED_BASE_URL,
    PUBMED_QUERY,
    PUBMED_MAX_RESULTS,
    PUBMED_DATE_FROM,
)

logger = logging.getLogger(__name__)


def _esearch(query: str, max_results: int, date_from: str) -> List[str]:
    """Recherche les PMIDs correspondant à la requête."""
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "mindate": date_from,
        "maxdate": "3000",
        "datetype": "pdat",
    }
    try:
        resp = requests.get(f"{PUBMED_BASE_URL}/esearch.fcgi", params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        pmids = data.get("esearchresult", {}).get("idlist", [])
        logger.info(f"🔍 PubMed esearch — {len(pmids)} PMIDs trouvés")
        return pmids
    except requests.RequestException as e:
        logger.error(f"❌ PubMed esearch error: {e}")
        return []


def _efetch(pmids: List[str]) -> ET.Element:
    """Récupère les détails XML pour une liste de PMIDs."""
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract",
    }
    try:
        resp = requests.get(f"{PUBMED_BASE_URL}/efetch.fcgi", params=params, timeout=60)
        resp.raise_for_status()
        return ET.fromstring(resp.content)
    except requests.RequestException as e:
        logger.error(f"❌ PubMed efetch error: {e}")
        return ET.Element("PubmedArticleSet")


def _parse_article(article: ET.Element) -> Dict:
    """Parse un article XML PubMed en document unifié."""
    medline = article.find("MedlineCitation")
    if medline is None:
        return {}

    # PMID
    pmid_el = medline.find("PMID")
    pmid = pmid_el.text if pmid_el is not None else ""

    art = medline.find("Article")
    if art is None:
        return {}

    # Titre
    title_el = art.find("ArticleTitle")
    title = "".join(title_el.itertext()) if title_el is not None else ""

    # Abstract
    abstract_el = art.find("Abstract")
    abstract_parts = []
    if abstract_el is not None:
        for text_el in abstract_el.findall("AbstractText"):
            label = text_el.get("Label", "")
            text = "".join(text_el.itertext())
            if label:
                abstract_parts.append(f"{label}: {text}")
            else:
                abstract_parts.append(text)
    abstract = "\n".join(abstract_parts)

    # Auteurs
    authors = []
    author_list = art.find("AuthorList")
    if author_list is not None:
        for author in author_list.findall("Author"):
            last = author.findtext("LastName", "")
            fore = author.findtext("ForeName", "")
            if last:
                authors.append(f"{last} {fore}".strip())

    # Journal
    journal_el = art.find("Journal")
    journal = ""
    pub_date = ""
    if journal_el is not None:
        journal = journal_el.findtext("Title", "")
        pub_date_el = journal_el.find("JournalIssue/PubDate")
        if pub_date_el is not None:
            year = pub_date_el.findtext("Year", "")
            month = pub_date_el.findtext("Month", "")
            pub_date = f"{year}-{month}" if month else year

    # Keywords
    keywords = []
    kw_list = medline.find("KeywordList")
    if kw_list is not None:
        keywords = [kw.text for kw in kw_list.findall("Keyword") if kw.text]

    # MeSH terms
    mesh_terms = []
    mesh_list = medline.find("MeshHeadingList")
    if mesh_list is not None:
        for mesh in mesh_list.findall("MeshHeading"):
            desc = mesh.findtext("DescriptorName", "")
            if desc:
                mesh_terms.append(desc)

    # Contenu enrichi
    content_parts = [
        f"Titre: {title}",
        f"Journal: {journal}" if journal else "",
        f"Auteurs: {', '.join(authors[:5])}" if authors else "",
        f"Mots-clés: {', '.join(keywords)}" if keywords else "",
        f"MeSH: {', '.join(mesh_terms[:10])}" if mesh_terms else "",
        f"Abstract: {abstract}" if abstract else "",
    ]
    content = "\n".join(p for p in content_parts if p)

    return {
        "id": f"pubmed_{pmid}",
        "source": "pubmed",
        "date": pub_date,
        "title": title,
        "content": content,
        "metadata": {
            "pmid": pmid,
            "journal": journal,
            "authors": authors,
            "keywords": keywords,
            "mesh_terms": mesh_terms[:10],
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        },
    }


def collect(max_results: int = PUBMED_MAX_RESULTS) -> List[Dict]:
    """
    Collecte les publications Sanofi depuis PubMed.

    Returns:
        Liste de documents au format unifié pipeline.
    """
    logger.info(f"🔍 PubMed — collecte '{PUBMED_QUERY}' depuis {PUBMED_DATE_FROM} (max {max_results})")

    pmids = _esearch(PUBMED_QUERY, max_results, PUBMED_DATE_FROM)
    if not pmids:
        return []

    # Fetch par batch de 20 pour éviter timeout
    batch_size = 20
    docs = []

    for i in range(0, len(pmids), batch_size):
        batch = pmids[i:i + batch_size]
        root = _efetch(batch)
        for article in root.findall("PubmedArticle"):
            doc = _parse_article(article)
            if doc:
                docs.append(doc)

    logger.info(f"✅ PubMed — {len(docs)} articles collectés")
    return docs