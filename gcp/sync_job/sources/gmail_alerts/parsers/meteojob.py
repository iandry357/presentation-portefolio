"""
Parseur emails Meteojob.
Expéditeur : ne-pas-repondre@meteojob.com

Structure HTML (template HOT_OFFER) :
  Chaque offre est ancrée sur un lien <a href="/jobs/{id}...">
  Titre       : <strong> dans le lien principal
  URL         : href → /jobs/{id_numerique}
  Entreprise  : premier <span> sans classe après le <strong>
  Localisation: <span class="hotoffer-locality-font-size">
  Contrat     : <span class="hotoffer-contract-font-size">

Filtre : emails marketing (ex. CANDIDATE_CREATE_RESUME_PUSH)
  ne contiennent pas de liens /jobs/{id} → liste vide retournée naturellement.
"""

import logging
import re
from datetime import datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from ..base_parser import BaseParser, OffreNormalisee

logger = logging.getLogger(__name__)

METEOJOB_BASE = "https://www.meteojob.com"


class MeteojobParser(BaseParser):

    def parse(self, html: str, email_date: datetime) -> list[OffreNormalisee]:
        try:
            return self._parse(html, email_date)
        except Exception as e:
            logger.error(f"[MeteojobParser] Erreur inattendue : {e}", exc_info=True)
            return []

    def _parse(self, html: str, email_date: datetime) -> list[OffreNormalisee]:
        soup = BeautifulSoup(html, "html.parser")
        offers = []
        seen_ids = set()

        recherche_mot_cle = None
        recherche_localisation = None
        criteria_badges = soup.find_all("p", style=lambda s: s and "background-color:#F3F5F6" in s)
        if len(criteria_badges) >= 1:
            recherche_mot_cle = criteria_badges[0].get_text(strip=True) or None
        if len(criteria_badges) >= 2:
            recherche_localisation = criteria_badges[1].get_text(strip=True) or None

        # Ancre fiable : tous les liens /jobs/{id} dans le document
        # job_links = soup.find_all(
        #     "a",
        #     href=lambda h: h and re.search(r"/jobs/\d+", h)
        # )
        job_links = [
            a for a in soup.find_all("a", href=lambda h: h and re.search(r"/jobs/\d+", h))
            if a.find("strong")
        ]

        for link in job_links:
            href = link.get("href", "").strip()
            match = re.search(r"/jobs/(\d+)", href)
            if not match:
                continue
            job_id = match.group(1)

            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            # Titre
            strong = link.find("strong")
            title = strong.get_text(strip=True) if strong else link.get_text(strip=True)
            if not title:
                continue

            # Remonter au td parent contenant l'offre complète
            parent_td = link.find_parent("td")

            company = None
            location = None
            contract = None

            if parent_td:
                # Entreprise : premier span sans classe après le strong du titre
                for span in parent_td.find_all("span"):
                    cls = span.get("class", [])
                    text = span.get_text(strip=True)
                    if not cls and text and text != title:
                        company = text
                        break

                # Localisation
                loc_span = parent_td.find("span", class_="hotoffer-locality-font-size")
                if loc_span:
                    location = loc_span.get_text(strip=True) or None

                # Contrat
                contract_span = parent_td.find("span", class_="hotoffer-contract-font-size")
                if contract_span:
                    contract = contract_span.get_text(strip=True) or None

            offer_url = f"{METEOJOB_BASE}/jobs/{job_id}"

            offers.append(OffreNormalisee(
                ft_id=None,
                offer_url=offer_url,
                title=title,
                company=company,
                location=location,
                contract=contract,
                source_offer="email_meteojob",
                source_branch="email_external",
                email_date=email_date,
                recherche_mot_cle=recherche_mot_cle,
                recherche_localisation=recherche_localisation,
            ))

        return offers