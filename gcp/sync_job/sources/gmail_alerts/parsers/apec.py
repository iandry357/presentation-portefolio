"""
Parseur emails APEC.
Expéditeur : offres@diffusion.apec.fr

Structure HTML : chaque offre dans un div.content
  Titre + URL : a[color:#0e6c8a, font-size:18px]
  Société     : a[color:#f38237]
  Contrat     : premier a[color:#444444] (attribut title)
  Lieu        : dernier a[color:#444444] (attribut title)
"""

import logging
from datetime import datetime

from bs4 import BeautifulSoup

from ..base_parser import BaseParser, OffreNormalisee

logger = logging.getLogger(__name__)


class ApecParser(BaseParser):

    def parse(self, html: str, email_date: datetime) -> list[OffreNormalisee]:
        try:
            return self._parse(html, email_date)
        except Exception as e:
            logger.error(f"[ApecParser] Erreur inattendue : {e}", exc_info=True)
            return []

    def _parse(self, html: str, email_date: datetime) -> list[OffreNormalisee]:
        soup = BeautifulSoup(html, "html.parser")
        offers = []
        seen_urls = set()

        for div in soup.find_all("div", class_="content"):
            title_tag = div.find("a", style=lambda s: s and "#0e6c8a" in s and "18px" in s)
            if not title_tag:
                continue

            url = title_tag.get("href", "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            title = title_tag.get_text(strip=True)
            if not title:
                continue

            company_tag = div.find("a", style=lambda s: s and "#f38237" in s)
            company = company_tag.get_text(strip=True) if company_tag else None

            grey_links = div.find_all("a", style=lambda s: s and "#444444" in s)
            contract = grey_links[0].get("title", "").strip() if len(grey_links) >= 1 else None
            location = grey_links[-1].get("title", "").strip() if len(grey_links) >= 2 else None

            if contract:
                contract = contract.replace("\xa0", "").replace("•", "").strip() or None

            offers.append(OffreNormalisee(
                ft_id=None,
                offer_url=url,
                title=title,
                company=company,
                location=location,
                contract=contract,
                source_offer="email_apec",
                source_branch="email_external",
                email_date=email_date,
            ))

        return offers