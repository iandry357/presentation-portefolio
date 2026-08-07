"""
Parseur emails LinkedIn Job Alerts.
Expéditeur : jobalerts-noreply@linkedin.com

Structure HTML : cards tr ou td[data-test-id=job-card]
  Titre + URL : a[class*=font-bold text-md]
  Société + Lieu : p[class*=text-system-gray-100 text-xs] → "Société · Ville (Mode travail)"
  Le mode de travail entre parenthèses est retiré de la localisation.
"""

import logging
import re
from datetime import datetime

from bs4 import BeautifulSoup

from ..base_parser import BaseParser, OffreNormalisee

logger = logging.getLogger(__name__)


class LinkedInParser(BaseParser):

    def parse(self, html: str, email_date: datetime) -> list[OffreNormalisee]:
        try:
            return self._parse(html, email_date)
        except Exception as e:
            logger.error(f"[LinkedInParser] Erreur inattendue : {e}", exc_info=True)
            return []

    @staticmethod
    def _split_company_location(raw: str):
        parts = raw.split("·")
        company = parts[0].strip() if parts else None
        location = None
        if len(parts) > 1:
            loc_raw = parts[1].strip()
            location = re.sub(r"\s*\(.*?\)", "", loc_raw).strip() or loc_raw
        return company or None, location

    def _parse(self, html: str, email_date: datetime) -> list[OffreNormalisee]:
        soup = BeautifulSoup(html, "html.parser")
        offers = []
        seen_urls = set()

        job_cards = soup.find_all(["tr", "td"], attrs={"data-test-id": "job-card"})

        if job_cards:
            # --- Template "Alerte Emploi" : mot-clé unique pour tout l'email ---
            recherche_mot_cle = None
            alert_text_node = soup.find(string=re.compile(r"Votre alerte Emploi pour"))
            if alert_text_node:
                strong = alert_text_node.find_next("strong")
                if strong:
                    recherche_mot_cle = strong.get_text(strip=True) or None

            for card in job_cards:
                links = card.find_all("a", href=lambda h: h and "linkedin.com/comm/jobs/view/" in h)
                if not links:
                    continue
                url = links[0]["href"].split("?")[0]
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                title_link = card.find("a", class_=lambda c: c and "text-md" in c)
                title = title_link.get_text(strip=True) if title_link else None
                if not title:
                    continue

                company = location = None
                company_tag = card.find("p", class_=lambda c: c and "text-system-gray-100" in c)
                if company_tag:
                    company, location = self._split_company_location(company_tag.get_text(strip=True))

                offers.append(OffreNormalisee(
                    ft_id=None,
                    offer_url=url,
                    title=title,
                    company=company,
                    location=location,
                    contract=None,
                    source_offer="email_linkedin",
                    source_branch="email_external",
                    email_date=email_date,
                    recherche_mot_cle=recherche_mot_cle,
                ))

        else:
            # --- Template "Recommandations" : mot-clé = catégorie LinkedIn, par section ---
            sections = soup.find_all("td", attrs={"data-test-id": "section-JOBS_POSTING_SECTION"})
            for section in sections:
                recherche_mot_cle = None
                title_link = section.find("a", attrs={"data-test-id": "title-link"})
                if title_link:
                    recherche_mot_cle = title_link.get_text(strip=True) or None

                job_links = section.find_all(
                    "a", href=lambda h: h and "linkedin.com/comm/jobs/view/" in h
                )
                for job_link in job_links:
                    url = job_link["href"].split("?")[0]
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    title_div = job_link.find(
                        "div", class_=lambda c: c and "font-bold" in c and "text-md" in c
                    )
                    title = title_div.get_text(strip=True) if title_div else None
                    if not title:
                        continue

                    company = location = None
                    company_tag = job_link.find(
                        "p", class_=lambda c: c and "text-system-gray-100" in c
                    )
                    if company_tag:
                        company, location = self._split_company_location(company_tag.get_text(strip=True))

                    offers.append(OffreNormalisee(
                        ft_id=None,
                        offer_url=url,
                        title=title,
                        company=company,
                        location=location,
                        contract=None,
                        source_offer="email_linkedin",
                        source_branch="email_external",
                        email_date=email_date,
                        recherche_mot_cle=recherche_mot_cle,
                    ))

        return offers