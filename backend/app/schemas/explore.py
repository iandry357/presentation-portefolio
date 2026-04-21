"""
Schémas Pydantic pour l'endpoint /explore.
"""

from typing import Optional
from pydantic import BaseModel


class ExploreOffer(BaseModel):
    id_unique: str
    source: str
    titre: str
    entreprise_nom: Optional[str] = None
    localisation_libelle: Optional[str] = None
    type_contrat: Optional[str] = None
    type_contrat_libelle: Optional[str] = None
    experience_libelle: Optional[str] = None
    salaire_libelle: Optional[str] = None
    salaire_min: Optional[float] = None
    salaire_max: Optional[float] = None
    salaire_present: bool = False
    code_rome: Optional[str] = None
    libelle_rome: Optional[str] = None
    url_offre: Optional[str] = None
    date_publication: Optional[str] = None
    date_collecte: Optional[str] = None


class ExploreResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    offers: list[ExploreOffer]


class FilterOptions(BaseModel):
    sources: list[str]
    types_contrat: list[str]
    regions: list[str]
    entreprise_nom: list[str]