from typing import List, Literal, Optional

from pydantic import BaseModel


# ============================================================================
# Statistiques (en-tête)
# ============================================================================

class StatsResponse(BaseModel):
    nb_dpe: int
    nb_passoires: int            # étiquettes F et G
    nb_remplacants: int          # DPE qui en remplacent un autre
    nb_ventes: int
    date_maj_dpe: Optional[str] = None
    date_maj_dvf: Optional[str] = None


# ============================================================================
# Parc DPE
# ============================================================================

class DpeLigne(BaseModel):
    arrondissement: Optional[int] = None
    etiquette_dpe: str
    flag_chauffage_electrique: bool
    nb_dpe: int
    nb_remplacants: int


class DpeResponse(BaseModel):
    lignes: List[DpeLigne]


# ============================================================================
# Prix DVF
# ============================================================================

class PrixLigne(BaseModel):
    arrondissement: Optional[int] = None
    annee: Optional[int] = None
    type_local: str
    nb_ventes: int
    prix_m2_median: Optional[float] = None


class PrixResponse(BaseModel):
    seuil_applique: bool         # vrai si l'accès est verrouillé : cellules de moins de `seuil` ventes retirées
    seuil: int
    nb_masquees: int
    lignes: List[PrixLigne]


# ============================================================================
# Changements (privé)
# ============================================================================

class ChangementLigne(BaseModel):
    numero_dpe: str
    date_etablissement_dpe: Optional[str] = None
    adresse_ban: Optional[str] = None
    arrondissement: Optional[int] = None
    etiquette_dpe: str
    type_energie_principale_chauffage: Optional[str] = None
    flag_chauffage_electrique: bool
    flag_post_reforme_2026: bool
    lecture: Literal["recalcul_2026_probable", "refait"]


class ChangementsResponse(BaseModel):
    total: int                   # DPE refaits après filtres, avant découpe
    page: int
    nb_pages: int
    taille: int
    nb_recalcul_probable: int    # parmi le total : chauffage électrique et DPE post-réforme
    lignes: List[ChangementLigne]
