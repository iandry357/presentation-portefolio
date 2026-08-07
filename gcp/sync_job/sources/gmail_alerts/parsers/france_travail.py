"""
Parseur emails France Travail.
Expéditeur : nepasrepondre@offre.francetravail.fr

Structure HTML : chaque offre dans une table[width=552]
  URL + ft_id : a[href*=candidat.francetravail.fr/offres/recherche/detail/{ft_id}]
  Titre       : span[font-size:20px, font-weight:700] — texte direct uniquement
  Société     : span[color:#2E2E31] (optionnelle)
  Lieu        : span[color:#5B5D65]
  Contrat     : span après img[src*=icon-sm-edit]
  Extrait     : p directement dans le tr suivant la ligne des icônes
"""

import logging
from datetime import datetime

from bs4 import BeautifulSoup

from ..base_parser import BaseParser, OffreNormalisee

import re

logger = logging.getLogger(__name__)

FT_DETAIL_PATTERN = "candidat.francetravail.fr/offres/recherche/detail/"


class FranceTravailParser(BaseParser):

    def parse(self, html: str, email_date: datetime) -> list[OffreNormalisee]:
        try:
            return self._parse(html, email_date)
        except Exception as e:
            logger.error(f"[FranceTravailParser] Erreur inattendue : {e}", exc_info=True)
            return []

    def _parse(self, html: str, email_date: datetime) -> list[OffreNormalisee]:
        soup = BeautifulSoup(html, "html.parser")
        offers = []
        seen_ft_ids = set()

        recherche_mot_cle = None
        header_text = soup.find(string=re.compile(r"pour votre alerte"))
        if header_text:
            kw_match = re.search(r'alerte\s+"(.+?)"', header_text)
            if kw_match:
                recherche_mot_cle = kw_match.group(1).strip()

        for a in soup.find_all("a", href=lambda h: h and FT_DETAIL_PATTERN in h):
            raw_url = a.get("href", "").split("?")[0]
            if not raw_url:
                continue

            # Extraire le ft_id depuis la fin du path
            ft_id = raw_url.rstrip("/").split("/")[-1]
            if not ft_id or ft_id in seen_ft_ids:
                continue
            seen_ft_ids.add(ft_id)

            # Titre : texte direct du span 20px/700 (exclut les spans enfants)
            title_span = a.find("span", style=lambda s: s and "20px" in s and "700" in s)
            if not title_span:
                continue
            title = "".join(
                t for t in title_span.strings
                if t.parent == title_span
            ).strip()
            if not title:
                continue

            # Société : span color #2E2E31 (optionnelle)
            company_span = a.find("span", style=lambda s: s and "#2E2E31" in s)
            company = company_span.get_text(strip=True).rstrip(" -").strip() if company_span else None
            company = company or None

            # Localisation : span color #5B5D65
            loc_span = a.find("span", style=lambda s: s and "#5B5D65" in s)
            location = loc_span.get_text(strip=True) if loc_span else None

            # Contrat : span après img icon-sm-edit dans la table parente width=552
            contract = None
            parent_table = a.find_parent("table", width="552")
            if parent_table:
                edit_img = parent_table.find("img", src=lambda s: s and "icon-sm-edit" in s)
                if edit_img:
                    contract_td = edit_img.find_parent("td")
                    if contract_td:
                        next_td = contract_td.find_next_sibling("td")
                        if next_td:
                            contract = next_td.get_text(strip=True) or None

            # Extrait de description : p dans le tr après les icônes
            description_excerpt = None
            if parent_table:
                desc_p = parent_table.find("p", style=lambda s: s and "margin-top:8px" in s)
                if desc_p:
                    description_excerpt = desc_p.get_text(strip=True) or None

            offers.append(OffreNormalisee(
                ft_id=ft_id,
                offer_url=raw_url,
                title=title,
                company=company,
                location=location,
                contract=contract,
                description_excerpt=description_excerpt,
                source_offer="email_france_travail",
                source_branch="email_ft",
                email_date=email_date,
                recherche_mot_cle=recherche_mot_cle,
            ))

        return offers