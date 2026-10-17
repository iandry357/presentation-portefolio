from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ============================================================================
# Top du jour
# ============================================================================

class TopOffre(BaseModel):
    """Une offre du top du jour (ligne de mart_top_du_jour)."""
    id_unique: str
    source: Optional[str] = None
    titre: str
    entreprise_nom: Optional[str] = None
    entreprise_normalise: Optional[str] = None
    localisation_libelle: Optional[str] = None
    type_contrat_libelle: Optional[str] = None
    salaire_libelle: Optional[str] = None
    url_offre: Optional[str] = None
    date_publication: Optional[str] = None
    date_collecte: Optional[str] = None
    score: Optional[int] = None
    categorie: Optional[str] = None
    raison: Optional[str] = None
    alertes: List[str] = []
    similarite: Optional[float] = None
    liste: Literal["a_lire", "zone_grise"]
    secteur: Optional[str] = None
    # Type affiché : la correction de l'utilisateur si elle existe, sinon l'automatique du mart
    type_entreprise: str
    type_entreprise_corrige: bool = False
    entreprise_exclue: bool = False


class TopCompteurs(BaseModel):
    a_lire: int
    zone_grise: int


class TopResponse(BaseModel):
    """Les deux listes (onglets) d'un coup, avec les compteurs pour les libellés d'onglets."""
    jours: int
    a_lire: List[TopOffre]
    zone_grise: List[TopOffre]
    compteurs: TopCompteurs


# ============================================================================
# Statistiques publiques (mart_stats, format long)
# ============================================================================

class StatLigne(BaseModel):
    jour: str
    dimension: str
    valeur: Optional[str] = None
    nb_offres: int


class StatsResponse(BaseModel):
    jours: int
    lignes: List[StatLigne]


# ============================================================================
# Décisions « intéressé / pas intéressé »
# ============================================================================

class DecisionCreate(BaseModel):
    """
    « pas_interesse » : enregistre la décision.
    « interesse » : crée un brouillon dans job_offers, après contrôle de doublon.
    Un doublon détecté n'est jamais bloquant : confirmer=True crée quand même le brouillon,
    utiliser_job_offer_id rattache la décision à une offre déjà présente dans job_offers.
    """
    id_unique: str = Field(..., min_length=1)
    decision: Literal["pas_interesse", "interesse"]
    confirmer: bool = False
    utiliser_job_offer_id: Optional[int] = None


class OffreProche(BaseModel):
    """Offre de job_offers qui ressemble à l'offre du top."""
    job_offer_id: int
    title: str
    company_name: Optional[str] = None
    status: str
    critere: Literal["ft_id", "titre_entreprise"]


class DecisionResponse(BaseModel):
    resultat: Literal["decision_enregistree", "doublon_detecte"]
    decision: Optional[str] = None
    job_offer_id: Optional[int] = None
    doublons: List[OffreProche] = []


# ============================================================================
# Types d'entreprise corrigés
# ============================================================================

class TypeEntrepriseUpdate(BaseModel):
    type_entreprise: Literal["esn", "conseil", "esn_conseil", "cabinet_recrutement", "client_final"]
    commentaire: Optional[str] = None


class TypeEntrepriseResponse(BaseModel):
    nom_normalise: str
    type_entreprise: str
    commentaire: Optional[str] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
