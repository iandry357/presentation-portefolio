"""
ParserRegistry — annuaire expéditeur → parseur.
Seul endroit du projet qui connaît le mapping source email → classe parseur.
Ajouter une nouvelle source = une ligne dans SENDER_MAP.
"""

import logging
from datetime import datetime

from .base_parser import BaseParser, OffreNormalisee
from .parsers.france_travail import FranceTravailParser
from .parsers.linkedin import LinkedInParser
from .parsers.apec import ApecParser
from .parsers.hellowork import HelloworkParser
from .parsers.talent import TalentParser

logger = logging.getLogger(__name__)

# Mapping expéditeur → instance parseur
SENDER_MAP: dict[str, BaseParser] = {
    "nepasrepondre@offre.francetravail.fr": FranceTravailParser(),
    "jobalerts-noreply@linkedin.com":       LinkedInParser(),
    "offres@diffusion.apec.fr":             ApecParser(),
    "notification@emails.hellowork.com":    HelloworkParser(),
    "no-reply@alerts.talent.com":           TalentParser(),
}


class ParserRegistry:

    def parse(self, sender: str, html: str, email_date: datetime) -> list[OffreNormalisee]:
        """
        Identifie le parseur depuis l'expéditeur et délègue.
        Retourne une liste vide si l'expéditeur est inconnu.
        """
        parser = SENDER_MAP.get(sender)
        if not parser:
            logger.warning(f"[ParserRegistry] Expéditeur inconnu : {sender}")
            return []

        offers = parser.parse(html, email_date)
        logger.info(f"[ParserRegistry] {sender} → {len(offers)} offre(s) extraite(s)")
        return offers