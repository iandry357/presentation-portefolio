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

        for li in soup.select("ul.alerts li"):
            try:
                # link = li.find("a", href=lambda h: h and "free-work.com" in h)
                link = li.find("a", href=True)
                if not link:
                    continue

                url = link["href"].split("?")[0]
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                # Titre — texte du <b> avant le span contrat
                bold = link.find("b")
                if not bold:
                    continue

                # Extraire le titre en retirant le span contrat du texte du <b>
                contract_span = bold.find(
                    "span", class_=lambda c: c and c in ("contractor", "worker")
                )
                contract = contract_span.get_text(strip=True) if contract_span else None

                # Titre = texte du <b> sans le span et sans le " - "
                if contract_span:
                    contract_span.extract()
                title_raw = bold.get_text(separator=" ", strip=True)
                title = re.sub(r"\s*-\s*$", "", title_raw).strip()
                if not title:
                    continue

                # Localisation — extraite du texte après <br>
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
                        # Format : "X mois - salaire - tjm - Localisation" ou "salaire - Localisation"
                        parts = [p.strip() for p in detail.split(" - ")]
                        # La localisation est toujours le dernier segment
                        location = parts[-1] if parts else None
                        # Le salaire est le segment contenant "€" ou "k€"
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
                ))

            except Exception as e:
                logger.warning(f"[FreeworkParser] Erreur offre : {e}")

        return offers