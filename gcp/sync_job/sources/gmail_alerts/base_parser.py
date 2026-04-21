"""
Contrat commun pour tous les parseurs Gmail.
OffreNormalisée est le seul objet qui traverse la frontière parsing → insertion.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class OffreNormalisee(BaseModel):
    """
    Représentation unifiée d'une offre extraite d'un email.

    Deux cas selon la source :
      - Offre France Travail email : ft_id renseigné, offer_url None
      - Offre autre source         : ft_id None, offer_url renseigné
    """

    # Identifiants — mutuellement exclusifs selon la source
    ft_id:       Optional[str] = None
    offer_url:   Optional[str] = None

    # Champs communs
    title:        str
    company:      Optional[str] = None
    location:     Optional[str] = None
    contract:     Optional[str] = None
    salary_label: Optional[str] = None

    # Extrait de description — disponible uniquement pour France Travail email
    description_excerpt: Optional[str] = None

    # Métadonnées source
    source_offer:  str           # ex: "email_france_travail", "email_linkedin"
    source_branch: str           # ex: "email_ft", "email_external"
    email_date:    datetime


class BaseParser(ABC):
    """
    Classe de base pour tous les parseurs de sources email.
    Chaque parseur concret implémente parse() pour sa source.
    """

    @abstractmethod
    def parse(self, html: str, email_date: datetime) -> list[OffreNormalisee]:
        """
        Prend le corps HTML d'un email et sa date.
        Retourne une liste d'OffreNormalisee (vide si rien extrait).
        Ne lève jamais d'exception — les erreurs sont loggées et ignorées.
        """
        ...