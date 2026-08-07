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

        recherche_mot_cle = None
        header_h2 = soup.find("h2")
        if header_h2:
            orange_spans = header_h2.find_all("span", class_="orange")
            if len(orange_spans) >= 2:
                recherche_mot_cle = orange_spans[-1].get_text(strip=True) or None

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

            # company_tag = div.find("a", style=lambda s: s and "#f38237" in s)
            # company = company_tag.get_text(strip=True) if company_tag else None
            # Récupération entreprise depuis l'URL du logo
            company = None
            logo_img = div.find("img", src=lambda s: s and "/logo_" in s)
            if logo_img:
                src = logo_img.get("src", "")
                # Extrait le nom depuis logo_NOM_ENTREPRISE_id1_id2.ext
                import re
                match = re.search(r"/logo_(.+?)_\d+_\d+\.", src)
                if match:
                    company = match.group(1).replace("_", " ").title()

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
                recherche_mot_cle=recherche_mot_cle,
            ))

        return offers