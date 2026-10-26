from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class MessageHistorique(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class AssistantRequete(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    historique: List[MessageHistorique] = Field(default_factory=list, max_length=6)  # derniers messages, du plus ancien au plus récent


class SourceCitee(BaseModel):
    reference: str                       # ex. « Loi n° 89-462 du 6 juillet 1989, art. 6 »
    type_texte: str                      # loi, code, décret, arrêté, BOFiP, loi de finances
    statut: str                          # « en vigueur »
    date_version: Optional[str] = None
    url: str


class AssistantReponse(BaseModel):
    reponse: str                         # citations [n] renumérotées dans l'ordre d'apparition
    sources: List[SourceCitee]           # construites par le serveur depuis les métadonnées, jamais par le LLM
    refus: bool                          # vrai si aucune source du corpus ne répond
    modele: Optional[str] = None
