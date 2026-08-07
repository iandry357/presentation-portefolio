"""
Parseur emails Free-Work.
Expéditeur : jobs@free-work.com

Structure HTML : offres groupées par alerte dans ul.alerts
  Chaque offre : <li><a href="...">
    Titre    : texte du <b> avant le " - "
    Contrat  : span.contractor (vert) ou span.worker (orange)
    Salaire + localisation : texte après <br> — format variable
      ex: "36 mois - 55k-70k € - 400-550 € - Paris, France"
      ex: "55k-62k € - 75017, Paris, Île-de-France"
    URL      : href du <a>
"""

import logging
import re
from datetime import datetime

from bs4 import BeautifulSoup

from ..base_parser import BaseParser, OffreNormalisee

logger = logging.getLogger(__name__)


class FreeworkParser(BaseParser):

    def parse(self, html: str, email_date: datetime) -> list[OffreNormalisee]:
        try:
            return self._parse(html, email_date)
        except Exception as e:
            logger.error(f"[FreeworkParser] Erreur inattendue : {e}", exc_info=True)
            return []

    def _parse(self, html: str, email_date: datetime) -> list[OffreNormalisee]:
        soup = BeautifulSoup(html, "html.parser")
        offers = []
        seen_urls = set()

        for ul in soup.select("ul.alerts"):
            # Mot-clé propre à ce bloc d'alerte : texte juste après
            # "N offres correspondant à votre alerte"
            recherche_mot_cle = None
            header_node = ul.find_previous(string=re.compile(r"correspondant à votre alerte"))
            if header_node:
                keyword_node = header_node.find_next(string=True)
                while keyword_node is not None and not keyword_node.strip():
                    keyword_node = keyword_node.find_next(string=True)
                if keyword_node:
                    recherche_mot_cle = keyword_node.strip()

            for li in ul.find_all("li", recursive=False):
                try:
                    link = li.find("a", href=True)
                    if not link:
                        continue

                    url = link["href"].split("?")[0]
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    bold = link.find("b")
                    if not bold:
                        continue

                    contract_span = bold.find(
                        "span", class_=lambda c: c and c in ("contractor", "worker")
                    )
                    contract = contract_span.get_text(strip=True) if contract_span else None
                    if contract_span:
                        contract_span.extract()
                    title_raw = bold.get_text(separator=" ", strip=True)
                    title = re.sub(r"\s*-\s*$", "", title_raw).strip()
                    if not title:
                        continue

                    location = None
                    salary_label = None
                    br = link.find("br")
                    if br and br.next_sibling:
                        raw_detail = br.next_sibling
                        if hasattr(raw_detail, "get_text"):
                            detail = raw_detail.get_text(strip=True)
                        else:
                            detail = str(raw_detail).strip()

                        if detail:
                            parts = [p.strip() for p in detail.split(" - ")]
                            location = parts[-1] if parts else None
                            for part in parts:
                                if "€" in part or "k€" in part:
                                    salary_label = part
                                    break

                    offers.append(OffreNormalisee(
                        ft_id=None,
                        offer_url=url,
                        title=title,
                        company="Free-Work",
                        location=location,
                        contract=contract,
                        salary_label=salary_label,
                        source_offer="email_freework",
                        source_branch="email_external",
                        email_date=email_date,
                        recherche_mot_cle=recherche_mot_cle,
                    ))

                except Exception as e:
                    logger.warning(f"[FreeworkParser] Erreur offre : {e}")

        return offers