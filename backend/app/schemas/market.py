from typing import Any, Literal
from pydantic import BaseModel, field_validator

# ── Filtres autorisés ─────────────────────────────────────────────────────────

PERIODES = Literal["7j", "30j", "90j"]
SOURCES = Literal[
    "toutes",
    "france_travail_api",
    "email_linkedin",
    "email_apec",
    "email_hellowork",
    "email_talent",
    "email_indeed",
    "email_wttj",
    "email_jobijoba",
    "email_freework",
]

# ── Requête entrante ──────────────────────────────────────────────────────────

class MarketQueryParams(BaseModel):
    periode: PERIODES = "30j"
    source: SOURCES = "toutes"

    @field_validator("periode")
    @classmethod
    def validate_periode(cls, v: str) -> str:
        allowed = {"7j", "30j", "90j"}
        if v not in allowed:
            raise ValueError(f"periode doit être parmi {allowed}")
        return v

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        allowed = {
            "toutes", "france_travail_api", "email_linkedin", "email_apec",
            "email_hellowork", "email_talent", "email_indeed", "email_wttj",
            "email_jobijoba", "email_freework",
        }
        if v not in allowed:
            raise ValueError(f"source doit être parmi {allowed}")
        return v


# ── Réponse générique ─────────────────────────────────────────────────────────

class MarketQueryResult(BaseModel):
    query_id: str
    titre: str
    description: str
    colonnes: list[str]
    lignes: list[dict[str, Any]]
    total: int
    params: MarketQueryParams


# ── Entreprises exclues ───────────────────────────────────────────────────────

class ExcludedCompanyAdd(BaseModel):
    nom: str

    @field_validator("nom")
    @classmethod
    def validate_nom(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("nom ne peut pas être vide")
        if len(v) > 200:
            raise ValueError("nom trop long (max 200 caractères)")
        return v


class ExcludedCompaniesResponse(BaseModel):
    entreprises: list[str]
    total: int