"""
Parseur emails JobLeads.
Expéditeur : mailer@jobleads.com

Structure HTML : chaque offre dans un div[border-top: 4px solid #F56462]
  Titre       : div[font-size:20px, font-weight:600 ou 700]
  Entreprise  : div[color:#6F6C68] ou div[color:#484745] (selon format email)
  Localisation: premier bullet point → partie avant "|"
  Contrat     : second bullet point → partie après "|"
  ID stable   : paramètre promotedJobs extrait de l'URL du CTA
"""

import logging
import re
from datetime import datetime
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from ..base_parser import BaseParser, OffreNormalisee

logger = logging.getLogger(__name__)


class JobleadsParser(BaseParser):

    def parse(self, html: str, email_date: datetime) -> list[OffreNormalisee]:
        try:
            return self._parse(html, email_date)
        except Exception as e:
            logger.error(f"[JobleadsParser] Erreur inattendue : {e}", exc_info=True)
            return []

    def _parse(self, html: str, email_date: datetime) -> list[OffreNormalisee]:
        soup = BeautifulSoup(html, "html.parser")
        offers = []
        seen_ids = set()

        # Chaque carte offre a une bordure rouge caractéristique en haut
        cards = soup.find_all(
            "div",
            style=lambda s: s and "4px solid #F56462" in s and "background-color: #ffffff" in s
        )

        for card in cards:
            # --- Titre ---
            title_div = card.find(
                "div",
                style=lambda s: s and "font-size: 20px" in s and (
                    "font-weight: 600" in s or "font-weight: 700" in s
                )
            )
            if not title_div:
                continue
            title = title_div.get_text(strip=True)
            if not title:
                continue

            # --- Entreprise ---
            # Deux couleurs possibles selon le type d'email JobLeads
            company = None
            for color in ("#6F6C68", "#484745"):
                tag = card.find("div", style=lambda s, c=color: s and c in s and "font-size: 16px" in s)
                if tag:
                    text = tag.get_text(strip=True)
                    # Ignorer les bullet points (localisation/salaire)
                    if text and not text.startswith("•"):
                        company = text
                        break

            # --- Bullet points : localisation et contrat/salaire ---
            location = None
            contract = None
            bullet_divs = card.find_all(
                "div",
                style=lambda s: s and "font-size: 16px" in s and (
                    "#6F6C68" in s or "#484745" in s
                )
            )
            bullets = [
                d.get_text(strip=True)
                for d in bullet_divs
                if d.get_text(strip=True).startswith("•") or
                   # Bullet peut être dans un td frère
                   d.get_text(strip=True) not in ("", company or "")
            ]
            # Filtrer uniquement les vraies lignes bullet (contenant "|" ou une ville)
            raw_bullets = [b.lstrip("•").strip() for b in bullets if "|" in b or any(
                kw in b for kw in ("Paris", "Lyon", "Remote", "Hybride", "Télétravail")
            )]

            if len(raw_bullets) >= 1:
                # Premier bullet : "Paris | Hybride" → localisation = "Paris"
                parts = raw_bullets[0].split("|")
                location = parts[0].strip() or None

            if len(raw_bullets) >= 2:
                # Second bullet : "EUR 80 000 - 100 000 | Plein temps" → contrat = "Plein temps"
                parts = raw_bullets[1].split("|")
                contract = parts[-1].strip() or None

            # --- URL + ID stable via paramètre promotedJobs ---
            offer_url = None
            job_id = None
            cta = card.find("a", href=lambda h: h and "jobleads.com" in h)
            if cta:
                href = cta.get("href", "")
                # Extraire le paramètre redirectBack pour avoir l'URL avec promotedJobs
                try:
                    parsed = urlparse(href)
                    qs = parse_qs(parsed.query)
                    redirect = qs.get("redirectBack", [None])[0]
                    if redirect:
                        redirect_parsed = urlparse(redirect)
                        redirect_qs = parse_qs(redirect_parsed.query)
                        promoted = redirect_qs.get("promotedJobs", [None])[0]
                        if promoted:
                            job_id = promoted  # ex: "external-8869d8cd245bb04a31f2e4b4fb07d90d"
                except Exception:
                    pass
                offer_url = href

            if not job_id:
                # Fallback : hash titre+entreprise pour éviter les doublons
                job_id = f"jobleads_{hash(title + (company or ''))}"

            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            offers.append(OffreNormalisee(
                ft_id=None,
                offer_url=offer_url,
                title=title,
                company=company,
                location=location,
                contract=contract,
                source_offer="email_jobleads",
                source_branch="email_external",
                email_date=email_date,
            ))

        return offers