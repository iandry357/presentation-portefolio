"""
Parseur emails Hellowork.
Expéditeur : notification@emails.hellowork.com

Structure HTML : cards td[class*=bg-dark-cards padding-cards]
  Titre + URL : a[style*=font-size:18px, color:#000000]
  Société     : td[style*=font-size:12px, line-height:16px] (texte direct)
  Badges      : td[style*=background-color:#F6F6F6, border-radius:4px]
                [0]=localisation, [1]=contrat, optionnel=salaire (contient a[href=#])
"""

import logging
from datetime import datetime

from bs4 import BeautifulSoup

from ..base_parser import BaseParser, OffreNormalisee

logger = logging.getLogger(__name__)


class HelloworkParser(BaseParser):

    def parse(self, html: str, email_date: datetime) -> list[OffreNormalisee]:
        try:
            return self._parse(html, email_date)
        except Exception as e:
            logger.error(f"[HelloworkParser] Erreur inattendue : {e}", exc_info=True)
            return []

    def _parse(self, html: str, email_date: datetime) -> list[OffreNormalisee]:
        soup = BeautifulSoup(html, "html.parser")
        offers = []
        seen_urls = set()

        for card in soup.find_all(
            "td", class_=lambda c: c and "bg-dark-cards" in c and "padding-cards" in c
        ):
            title_tag = card.find("a", style=lambda s: s and "font-size:18px" in s and "#000000" in s)
            if not title_tag:
                continue

            url = title_tag.get("href", "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            title = title_tag.get_text(strip=True)
            if not title:
                continue

            company = None
            for td in card.find_all("td", style=lambda s: s and "font-size:12px" in s and "line-height:16px" in s):
                text = td.get_text(strip=True)
                if text and len(text) > 1:
                    company = text
                    break

            badges = card.find_all(
                "td", style=lambda s: s and "background-color:#F6F6F6" in s and "border-radius:4px" in s
            )
            non_salary = [b for b in badges if not b.find("a", href="#")]
            salary_badges = [b for b in badges if b.find("a", href="#")]

            location = non_salary[0].get_text(strip=True) or None if len(non_salary) >= 1 else None
            contract = non_salary[1].get_text(strip=True) or None if len(non_salary) >= 2 else None
            salary_label = salary_badges[0].get_text(strip=True) or None if salary_badges else None

            offers.append(OffreNormalisee(
                ft_id=None,
                offer_url=url,
                title=title,
                company=company,
                location=location,
                contract=contract,
                salary_label=salary_label,
                source_offer="email_hellowork",
                source_branch="email_external",
                email_date=email_date,
            ))

        return offers