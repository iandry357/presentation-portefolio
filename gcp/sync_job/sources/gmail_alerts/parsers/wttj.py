"""
Parseur emails Welcome to the Jungle.
Expéditeur : alerts@welcometothejungle.com

Structure HTML : table.job-item — une par offre
  Entreprise   : td[style*="color: #737373"] > a > texte
  Titre        : td[style*="color: #000000"] > a > texte (font-weight:700)
  Contrat+Lieu : td[style*="color: #4C4C4C"] > a > texte — format "CDI - Paris"
  URL          : href du a dans td[style*="color: #000000"]
"""

import logging
from datetime import datetime

from bs4 import BeautifulSoup

from ..base_parser import BaseParser, OffreNormalisee

logger = logging.getLogger(__name__)


class WTTJParser(BaseParser):

    def parse(self, html: str, email_date: datetime) -> list[OffreNormalisee]:
        try:
            return self._parse(html, email_date)
        except Exception as e:
            logger.error(f"[WTTJParser] Erreur inattendue : {e}", exc_info=True)
            return []

    def _parse(self, html: str, email_date: datetime) -> list[OffreNormalisee]:
        soup = BeautifulSoup(html, "html.parser")
        offers = []
        seen_urls = set()

        for item in soup.find_all("table", class_="job-item"):
            try:
                inner = item.find("table", class_="job-item-inner")
                # logger.info(f"[WTTJParser] inner={'trouvé' if inner else 'ABSENT'}")
                # if inner:
                #     title_td = inner.find(
                #         "td", style=lambda s: s and "font-weight: 700" in s and "color: #000000" in s
                #     )
                #     logger.info(f"[WTTJParser] title_td={'trouvé' if title_td else 'ABSENT'}")
                # break
                if not inner:
                    continue

                # Titre + URL — td avec font-weight:700
                # title_td = inner.find(
                #     "td", style=lambda s: s and "font-weight: 700" in s and "color: #000000" in s
                # )
                title_td = inner.find(
                    "td", style=lambda s: s and "font-size: 20px" in s and "color: #000000" in s
                )
                if not title_td:
                    continue
                title_link = title_td.find("a", href=True)
                # if title_link:
                #     url = title_link["href"].split("?")[0]
                #     logger.info(f"[WTTJParser] url={url[:80]}")
                if not title_link:
                    continue
                title = title_link.get_text(strip=True)
                # URL complète (tracking) — on garde telle quelle pour offer_url
                url = title_link["href"]
                if not url:
                    continue

                # Déduplication sur le titre (URL non exploitable)
                if title in seen_urls:
                    continue
                seen_urls.add(title)

                # Entreprise — td avec color: #737373
                company_td = inner.find(
                    "td", style=lambda s: s and "color: #737373" in s
                )
                company = None
                if company_td:
                    company_link = company_td.find("a")
                    company = company_link.get_text(strip=True) if company_link else None

                # Contrat + Localisation — td avec color: #4C4C4C
                detail_td = inner.find(
                    "td", style=lambda s: s and "color: #4C4C4C" in s
                )
                contract = location = None
                if detail_td:
                    detail_link = detail_td.find("a")
                    if detail_link:
                        raw = detail_link.get_text(strip=True)
                        # Format : "CDI - Paris" ou "CDI - Courbevoie"
                        parts = [p.strip() for p in raw.split(" - ")]
                        contract = parts[0] if parts else None
                        location = parts[1] if len(parts) > 1 else None

                offers.append(OffreNormalisee(
                    ft_id=None,
                    offer_url=url,
                    title=title,
                    company=company,
                    location=location,
                    contract=contract,
                    source_offer="email_wttj",
                    source_branch="email_external",
                    email_date=email_date,
                ))

            except Exception as e:
                logger.warning(f"[WTTJParser] Erreur offre : {e}")



        items = soup.find_all("table", class_="job-item")
        logger.info(f"[WTTJParser] {len(items)} job-item trouvés")

        return offers