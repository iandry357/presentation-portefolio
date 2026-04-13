"""
Parseur emails Indeed Job Alerts.
Expéditeur : donotreply@jobalert.indeed.com

Structure HTML : td[class*="r-d"] — un par offre
  Titre        : a[style*="text-decoration:underline"] → texte
  Entreprise   : span.r-i → texte
  Localisation : span.r-j → texte (format "- Paris (75)")
  Description  : td.r-l → texte
  Salaire      : td.r-k → texte (optionnel)
  URL          : href du <a> parent wrappant l'offre
"""

import logging
import re
from datetime import datetime

from bs4 import BeautifulSoup

from ..base_parser import BaseParser, OffreNormalisee

logger = logging.getLogger(__name__)


class IndeedParser(BaseParser):

    def parse(self, html: str, email_date: datetime) -> list[OffreNormalisee]:
        try:
            return self._parse(html, email_date)
        except Exception as e:
            logger.error(f"[IndeedParser] Erreur inattendue : {e}", exc_info=True)
            return []

    def _parse(self, html: str, email_date: datetime) -> list[OffreNormalisee]:
        soup = BeautifulSoup(html, "html.parser")
        offers = []
        seen_urls = set()

        for td in soup.find_all("td", class_=lambda c: c and "r-d" in c.split()):
            try:
                # URL — href du <a> wrappant tout le bloc
                wrapper = td.find("a", href=lambda h: h and "engage.indeed.com" in h)
                if not wrapper:
                    continue
                url = wrapper["href"].split("?")[0]
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                # Titre — a[style*="text-decoration:underline"]
                title_link = wrapper.find(
                    "a", style=lambda s: s and "text-decoration:underline" in s
                )
                title = title_link.get_text(strip=True) if title_link else None
                if not title:
                    continue

                # Entreprise
                company_span = wrapper.find("span", class_="r-i")
                company = company_span.get_text(strip=True) if company_span else None

                # Localisation — span.r-j, format "- Paris (75)"
                location = None
                loc_span = wrapper.find("span", class_="r-j")
                if loc_span:
                    raw_loc = loc_span.get_text(strip=True)
                    location = re.sub(r"^-\s*", "", raw_loc).strip()

                # Description
                desc_td = wrapper.find("td", class_="r-l")
                description = desc_td.get_text(strip=True) if desc_td else None

                # Salaire — td.r-k (optionnel)
                salary_td = wrapper.find("td", class_="r-k")
                salary_label = salary_td.get_text(strip=True) if salary_td else None

                offers.append(OffreNormalisee(
                    ft_id=None,
                    offer_url=url,
                    title=title,
                    company=company,
                    location=location,
                    contract=None,
                    salary_label=salary_label,
                    description_excerpt=description,
                    source_offer="email_indeed",
                    source_branch="email_external",
                    email_date=email_date,
                ))

            except Exception as e:
                logger.warning(f"[IndeedParser] Erreur offre : {e}")

        return offers