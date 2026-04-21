"""
Parseur emails Jobijoba.
Expéditeur : contact@jobijoba.com

Structure HTML : table.row-34 — une par offre
  Titre        : span[style*="color: #002977"]
  Entreprise   : span[style*="color:#000000"]
  Localisation : span sans style entre les séparateurs " - "
  Contrat      : span après le second " - "
  Description  : span[style*="color: #4D5562"]
  URL          : href du <a> wrappant le bloc (URL trackée Jobijoba)
"""

import logging
from datetime import datetime

from bs4 import BeautifulSoup

from ..base_parser import BaseParser, OffreNormalisee

logger = logging.getLogger(__name__)


class JobijobaParser(BaseParser):

    def parse(self, html: str, email_date: datetime) -> list[OffreNormalisee]:
        try:
            return self._parse(html, email_date)
        except Exception as e:
            logger.error(f"[JobijobaParser] Erreur inattendue : {e}", exc_info=True)
            return []

    def _parse(self, html: str, email_date: datetime) -> list[OffreNormalisee]:
        soup = BeautifulSoup(html, "html.parser")
        offers = []
        seen_urls = set()

        for row in soup.find_all("table", class_="row-34"):
            try:
                # URL — href du <a> wrappant le bloc
                link = row.find("a", href=lambda h: h and "jobijoba.com" in h)
                if not link:
                    continue
                url = link["href"].split("?")[0]
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                # Titre
                title_span = link.find(
                    "span", style=lambda s: s and "color: #002977" in s
                )
                title = title_span.get_text(strip=True) if title_span else None
                if not title:
                    continue

                # Entreprise
                company_span = link.find(
                    "span", style=lambda s: s and "color:#000000" in s
                )
                company = company_span.get_text(strip=True) if company_span else None

                # Localisation + Contrat — extraits du paragraphe principal
                location = contract = None
                para = link.find("p")
                if para:
                    raw = para.get_text(separator="|", strip=True)
                    parts = [p.strip() for p in raw.split("|") if p.strip()]
                    # Format attendu : Titre | Entreprise - Localisation - Contrat | Description
                    for part in parts:
                        if " - " in part and company and company in part:
                            segments = [s.strip() for s in part.split(" - ")]
                            # segments[0] = entreprise, [1] = localisation, [2] = contrat
                            if len(segments) >= 2:
                                location = segments[1] if len(segments) > 1 else None
                            if len(segments) >= 3:
                                contract = segments[2]

                # Description
                desc_span = link.find(
                    "span", style=lambda s: s and "color: #4D5562" in s
                )
                description = desc_span.get_text(strip=True) if desc_span else None

                offers.append(OffreNormalisee(
                    ft_id=None,
                    offer_url=url,
                    title=title,
                    company=company,
                    location=location,
                    contract=contract,
                    description_excerpt=description,
                    source_offer="email_jobijoba",
                    source_branch="email_external",
                    email_date=email_date,
                ))

            except Exception as e:
                logger.warning(f"[JobijobaParser] Erreur offre : {e}")

        return offers