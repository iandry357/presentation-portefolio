from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


# ------------------------------------------------------------
# Schéma de création — trigger initial
# ------------------------------------------------------------

class CompanyProfileCreate(BaseModel):
    """Payload reçu pour déclencher la génération d'une fiche entreprise."""
    name_input: str                  # nom brut saisi ou détecté depuis l'offre
    job_offer_id: Optional[int] = None  # offre source pour lier la FK


# ------------------------------------------------------------
# Schéma résumé — liste des entreprises
# ------------------------------------------------------------

class CompanyProfileSummary(BaseModel):
    """Version légère pour la page liste /companies."""
    id:                   int
    name:                 str
    name_input:           str
    discovery_status:     str
    legal_status:         str
    actualites_status:    str
    memo_status:          str
    recalcul_count:       int
    actualites_updated_at: Optional[datetime]
    created_at:           datetime
    updated_at:           datetime

    model_config = {"from_attributes": True}


# ------------------------------------------------------------
# Schéma complet — JobDetail + page détail /companies/[id]
# ------------------------------------------------------------

class CompanyProfileDetail(BaseModel):
    """Version complète incluant toutes les couches de données."""
    id:                   int
    name:                 str
    name_input:           str

    # Données par couche
    discovery:            Optional[Any]  # JSON Agent 1
    legal_data:           Optional[Any]  # JSON Agent 2
    actualites:           Optional[Any]  # JSON refresh
    memo:                 Optional[str]  # Markdown Agent 3

    # Statuts par couche
    discovery_status:     str
    legal_status:         str
    actualites_status:    str
    memo_status:          str

    # Contrôle mémo
    recalcul_count:       int
    recalcul_history:     list

    # Horodatage
    actualites_updated_at: Optional[datetime]
    created_at:           datetime
    updated_at:           datetime

    model_config = {"from_attributes": True}


# ------------------------------------------------------------
# Schéma action — Actualiser les infos
# ------------------------------------------------------------

class CompanyRefreshRequest(BaseModel):
    """Payload pour relancer Agent 2 + refresh actualités + Agent 3.
    Pas de paramètre nécessaire — repart des URLs en discovery."""
    pass


# ------------------------------------------------------------
# Schéma action — Regénérer le mémo
# ------------------------------------------------------------

class CompanyRecalculRequest(BaseModel):
    """Payload pour relancer Agent 3 uniquement.
    instruction est optionnelle — si absente, repart du prompt initial."""
    instruction: Optional[str] = None


# ------------------------------------------------------------
# Schéma réponse générique — actions async
# ------------------------------------------------------------

class CompanyActionResponse(BaseModel):
    """Réponse immédiate après déclenchement d'une action async."""
    company_profile_id: int
    message:            str