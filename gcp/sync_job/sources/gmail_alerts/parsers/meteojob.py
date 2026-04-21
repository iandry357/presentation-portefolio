"""
Parseur emails Meteojob.
Expéditeur : ne-pas-repondre@meteojob.com

Structure HTML : chaque offre dans un tr > td[border-bottom:#f0f4f7 3px solid]
  Titre       : strong dans le lien a principal
  URL         : href du lien a → /jobs/{id_numerique} → ID Meteojob direct
  Entreprise  : texte du font après br, partie avant premier "•"
  Contrat     : partie entre le premier et le second "•"
  Localisation: partie après le second "•"

Filtre : emails de confirmation candidature et mise à jour profil
  ne contiennent pas cette structure → liste vide retournée naturellement.
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

        # Chaque offre est dans un td avec bordure grise en bas
        offer_tds = soup.find_all(
            "td",
            style=lambda s: s and "border-bottom" in s and "#f0f4f7" in s and "3px solid" in s
        )

        for td in offer_tds:
            # --- Lien principal + titre ---
            link = td.find("a", href=lambda h: h and "/jobs/" in h)
            if not link:
                continue

            href = link.get("href", "").strip()
            if not href:
                continue

            # Extraire l'ID numérique Meteojob depuis /jobs/{id}
            match = re.search(r"/jobs/(\d+)", href)
            if not match:
                continue
            job_id = match.group(1)

            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            # Titre dans le strong
            strong = link.find("strong")
            title = strong.get_text(strip=True) if strong else link.get_text(strip=True)
            if not title:
                continue

            # URL propre sans paramètres de tracking
            offer_url = f"{METEOJOB_BASE}/jobs/{job_id}"

            # --- Entreprise, contrat, localisation ---
            # Format dans le font : "Entreprise • Contrat • Ville (code) - Région"
            company = None
            contract = None
            location = None

            font_tag = link.find("font", style=lambda s: s and "font-weight:normal" in s)
            if font_tag:
                raw = font_tag.get_text(separator=" ", strip=True)
                # Nettoyer les espaces multiples et l'icône météo (texte alt "Météo")
                raw = re.sub(r"\s+", " ", raw).replace("Météo", "").strip()
                parts = [p.strip() for p in raw.split("•") if p.strip()]

                if len(parts) >= 1:
                    company = parts[0] or None
                if len(parts) >= 2:
                    contract = parts[1] or None
                if len(parts) >= 3:
                    # "Paris (75) - Île-de-France" → on garde tel quel
                    location = parts[2] or None

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
            ))

        return offers