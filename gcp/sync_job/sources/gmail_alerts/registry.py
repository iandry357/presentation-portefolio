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
from .parsers.jobijoba import JobijobaParser
from .parsers.freework import FreeworkParser
from .parsers.wttj import WTTJParser
from .parsers.indeed import IndeedParser
from .parsers.jobleads import JobleadsParser
from .parsers.meteojob import MeteojobParser

logger = logging.getLogger(__name__)

# Mapping expéditeur → instance parseur
SENDER_MAP: dict[str, BaseParser] = {
    "nepasrepondre@offre.francetravail.fr": FranceTravailParser(),
    "jobalerts-noreply@linkedin.com":       LinkedInParser(),
    "jobs-listings@linkedin.com":       LinkedInParser(),
    "offres@diffusion.apec.fr":             ApecParser(),
    "notification@emails.hellowork.com":    HelloworkParser(),
    "alerte@emails.hellowork.com":          HelloworkParser(),
    "no-reply@alerts.talent.com":           TalentParser(),
    "contact@jobijoba.com": JobijobaParser(),
    "jobs@free-work.com":   FreeworkParser(),
    "alerts@welcometothejungle.com":    WTTJParser(),
    "donotreply@jobalert.indeed.com":   IndeedParser(),
    "mailer@jobleads.com": JobleadsParser(),
    "ne-pas-repondre@meteojob.com": MeteojobParser(),
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