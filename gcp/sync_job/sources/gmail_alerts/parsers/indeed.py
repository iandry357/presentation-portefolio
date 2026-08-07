"""
Parseur emails Indeed Job Alerts.
Expéditeur : donotreply@jobalert.indeed.com

Structure HTML (design Aurora — validé avril 2026) :
  Bloc offre   : td.pb-24
  URL          : href du <a> direct enfant → fr.indeed.com/rc/clk/dl ou /pagead/clk/dl
  Titre        : <h2> → <a style*="text-decoration:underline"> → texte
  Entreprise   : premier <td> après <h2> dans la table imbriquée (sans img)
  Localisation : <td> standalone contenant ville au format "Paris (75)"
  Salaire      : <td> dans <table bgcolor="#f3f2f1"> (optionnel)
  Description  : <td> avec color:#767676 et font-size:14px (optionnel)
"""

import logging
import re
from datetime import datetime

from bs4 import BeautifulSoup

from ..base_parser import BaseParser, OffreNormalisee

logger = logging.getLogger(__name__)

# Regex pour détecter une localisation (ville + code postal optionnel)
_LOC_RE = re.compile(r"[A-ZÀ-Ö][a-zà-ö\-]+.*?\(\d{2,5}\)|[A-ZÀ-Ö][a-zà-ö\-]+.*?\d{2,5}")
_HEADER_RE = re.compile(r"^\d+\s+nouveaux?\s+emplois?\s+(.+?)\s+-\s+(.+)$", re.IGNORECASE)

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

        all_h2 = soup.find_all("h2")

        # --- Mot-clé / localisation : en-tête unique en haut de l'email ---
        # Ex: "30 nouveaux emplois machine learning engineer - Paris (75)"
        recherche_mot_cle = None
        recherche_localisation = None
        if all_h2:
            header_match = self._HEADER_RE.match(all_h2[0].get_text(strip=True))
            if header_match:
                recherche_mot_cle = header_match.group(1).strip()
                recherche_localisation = header_match.group(2).strip()

        for h2 in all_h2:
            try:
                # Ancrage par offre : le h2 doit contenir un lien direct vers l'offre
                # (exclut l'en-tête de digest qui n'a pas de tel lien)
                wrapper = h2.find(
                    "a",
                    href=lambda h: h and (
                        "fr.indeed.com/rc/clk" in h
                        or "fr.indeed.com/pagead/clk" in h
                    ),
                )
                if not wrapper:
                    continue

                raw_url = wrapper.get("href", "")
                jk_match = re.search(r"[?&]jk=([a-f0-9]+)", raw_url)
                dedup_key = jk_match.group(1) if jk_match else raw_url.split("?")[0]
                if dedup_key in seen_urls:
                    continue
                seen_urls.add(dedup_key)

                url = raw_url
                title = wrapper.get_text(strip=True)
                if not title:
                    continue

                # Bloc titre+entreprise+localisation : table immédiatement parente du h2
                row1_table = h2.find_parent("table")
                company = None
                location = None
                if row1_table:
                    rows = row1_table.find_all("tr", recursive=False)
                    if len(rows) >= 2:
                        paragraphs = rows[1].find_all("p")
                        if len(paragraphs) >= 1:
                            company = paragraphs[0].get_text(strip=True) or None
                        if len(paragraphs) >= 2:
                            location = paragraphs[1].get_text(strip=True) or None

                # Bloc offre complet (englobe aussi la ligne salaire, sœur de row1_table)
                offer_block = row1_table.find_parent("table") if row1_table else None

                salary_label = None
                if offer_block:
                    salary_table = offer_block.find("table", attrs={"bgcolor": "#f3f2f1"})
                    if salary_table:
                        salary_td = salary_table.find("td")
                        if salary_td:
                            salary_label = salary_td.get_text(strip=True)

                # Description : Indeed a retiré ce champ du template (vérifié —
                # color:#767676 ne sert plus qu'à la date relative "il y a X jours")
                description = None

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
                    recherche_mot_cle=recherche_mot_cle,
                    recherche_localisation=recherche_localisation,
                ))

            except Exception as e:
                logger.warning(f"[IndeedParser] Erreur offre : {e}")

        logger.info(f"[IndeedParser] {len(offers)} offres extraites")
        return offers