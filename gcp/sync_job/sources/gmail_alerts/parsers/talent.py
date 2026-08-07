"""
Parseur emails Talent.com.
Expéditeur : no-reply@alerts.talent.com

Structure HTML : enveloppe a[href*=talent.com/redirect, style*=display: block]
  contenant une table[bgcolor=#FFFFFF]
  Titre : a[style*=color:#30183f, font-size:18px]  (Template 1)
        | td[style*=color:#30183F, font-size:18px] (Template 2)
  Lieu  : td[style*=color:#691f74, font-size:14px]
  Société : td[style*=color:#30183f, font-size:14px] sans lien ni table imbriquée
"""

import logging
from datetime import datetime

from bs4 import BeautifulSoup

from ..base_parser import BaseParser, OffreNormalisee

import re

logger = logging.getLogger(__name__)


class TalentParser(BaseParser):

    def parse(self, html: str, email_date: datetime) -> list[OffreNormalisee]:
        try:
            return self._parse(html, email_date)
        except Exception as e:
            logger.error(f"[TalentParser] Erreur inattendue : {e}", exc_info=True)
            return []

    def _parse(self, html: str, email_date: datetime) -> list[OffreNormalisee]:
        soup = BeautifulSoup(html, "html.parser")
        offers = []
        # seen_urls = set()
        seen_titles = set()

        recherche_mot_cle = None
        recherche_localisation = None
        header_h1 = soup.find("h1")
        if header_h1:
            kw_match = re.search(r"pour\s+(.+)$", header_h1.get_text(strip=True))
            if kw_match:
                recherche_mot_cle = kw_match.group(1).strip()
            header_h2 = header_h1.find_next_sibling("h2")
            if header_h2:
                recherche_localisation = header_h2.get_text(strip=True) or None

        for outer_a in soup.find_all(
            "a",
            href=lambda h: h and "talent.com/redirect" in h,
            style=lambda s: s and "display: block" in s,
        ):
            url = outer_a.get("href", "").strip()
            if not url:
                continue

            card_table = outer_a.find("table", bgcolor="#FFFFFF")
            if not card_table:
                continue
            
            # Titre
            title_tag = card_table.find("a", style=lambda s: s and "#30183f" in s.lower() and "18px" in s)
            if title_tag:
                title = title_tag.get_text(strip=True)
            else:
                title_td = card_table.find("td", style=lambda s: s and "#30183f" in s.lower() and "18px" in s)
                title = title_td.get_text(strip=True) if title_td else None
            if not title:
                continue

            # Déduplication sur titre
            if title in seen_titles:
                continue
            seen_titles.add(title)

            # Localisation : td violet #691f74
            loc_tag = card_table.find("td", style=lambda s: s and "#691f74" in s and "14px" in s)
            location = loc_tag.get_text(strip=True) if loc_tag else None

            # Société : td sombre #30183f 14px, sans lien ni table imbriquée
            company = None
            for td in card_table.find_all("td", style=lambda s: s and "#30183f" in s and "14px" in s):
                if not td.find("a") and not td.find("table"):
                    text = td.get_text(strip=True)
                    if text:
                        company = text
                        break

            offers.append(OffreNormalisee(
                ft_id=None,
                offer_url=url,
                title=title,
                company=company,
                location=location,
                contract=None,
                source_offer="email_talent",
                source_branch="email_external",
                email_date=email_date,
                recherche_mot_cle=recherche_mot_cle,
                recherche_localisation=recherche_localisation,
            ))

        return offers