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

        for td in soup.find_all("td", class_="pb-24"):
            try:
                # URL — <a> direct enfant pointant vers indeed
                wrapper = td.find(
                    "a",
                    href=lambda h: h and (
                        "fr.indeed.com/rc/clk" in h
                        or "fr.indeed.com/pagead/clk" in h
                    ),
                )
                if not wrapper:
                    continue

                # Déduplication sur le job key (paramètre jk= dans l'URL)
                raw_url = wrapper.get("href", "")
                jk_match = re.search(r"[?&]jk=([a-f0-9]+)", raw_url)
                dedup_key = jk_match.group(1) if jk_match else raw_url.split("?")[0]
                if dedup_key in seen_urls:
                    continue
                seen_urls.add(dedup_key)

                # URL propre — on conserve l'URL complète (tracking Indeed)
                url = raw_url

                # Titre — <h2> > <a style*="text-decoration:underline">
                h2 = wrapper.find("h2")
                if not h2:
                    continue
                title_link = h2.find(
                    "a", style=lambda s: s and "text-decoration:underline" in s
                )
                title = title_link.get_text(strip=True) if title_link else h2.get_text(strip=True)
                if not title:
                    continue

                # Entreprise — premier <td> dans la table juste après le h2
                # qui ne contient pas d'image et dont le texte est non vide
                company = None
                company_table = h2.find_next_sibling("tr")
                if company_table:
                    for td_cell in company_table.find_all("td"):
                        text = td_cell.get_text(strip=True)
                        if text and not td_cell.find("img"):
                            company = text
                            break

                # Localisation — <td> standalone avec texte court ressemblant à une ville
                location = None
                for td_cell in wrapper.find_all("td"):
                    style = td_cell.get("style", "")
                    # Les tds de localisation ont color:#2d2d2d, font-size:14px
                    # et contiennent uniquement du texte (pas de table imbriquée)
                    if (
                        "color:#2d2d2d" in style
                        and "font-size:14px" in style
                        and not td_cell.find("table")
                        and not td_cell.find("a")
                    ):
                        text = td_cell.get_text(strip=True)
                        # Filtre : texte court (< 60 chars), pas une description
                        if text and len(text) < 60 and not text.endswith("…"):
                            location = text
                            break

                # Salaire — <td> dans <table bgcolor="#f3f2f1">
                salary_label = None
                salary_table = wrapper.find("table", attrs={"bgcolor": "#f3f2f1"})
                if salary_table:
                    salary_td = salary_table.find("td")
                    if salary_td:
                        salary_label = salary_td.get_text(strip=True)

                # Description — <td> avec color:#767676 et font-size:14px
                description = None
                for td_cell in wrapper.find_all("td"):
                    style = td_cell.get("style", "")
                    if "color:#767676" in style and "font-size:14px" in style:
                        text = td_cell.get_text(strip=True)
                        # Exclure les tds de date ("il y a X jours", "Publié à l'instant")
                        if text and "jour" not in text.lower() and "instant" not in text.lower():
                            description = text
                            break

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

        logger.info(f"[IndeedParser] {len(offers)} offres extraites")
        return offers