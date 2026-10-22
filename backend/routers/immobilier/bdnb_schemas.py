from typing import List, Optional

from pydantic import BaseModel


# ============================================================================
# Statistiques (bandeau)
# ============================================================================

class BdnbStatsResponse(BaseModel):
    nb_batiments: int
    nb_dpe: int                  # DPE retenus (arrêté 2021, logement, 3cl, surface > 0)
    nb_adresses: int
    nb_transactions: int         # transactions DVF représentatives (une par bâtiment)
    millesime: Optional[str] = None   # millésime de la BDNB (table bdnb_sources)
    date_maj: Optional[str] = None


# ============================================================================
# Prix et performance énergétique
# ============================================================================

class PrixDpeLigne(BaseModel):
    classe_dpe: str              # classe médiane des DPE du bâtiment
    nb_ventes: int
    prix_m2_median: Optional[float] = None


class EcartPrix(BaseModel):
    nb_fg: int
    prix_m2_median_fg: Optional[float] = None
    nb_d: int
    prix_m2_median_d: Optional[float] = None
    ecart_pct: Optional[float] = None  # (médiane F+G / médiane D - 1) x 100, arrondi à 0,1 ; brut, non corrigé


class PrixDpeResponse(BaseModel):
    seuil_applique: bool         # vrai si l'accès est verrouillé : classes de moins de `seuil` ventes retirées
    seuil: int
    nb_masquees: int
    date_vente_min: Optional[str] = None   # ventes retenues depuis cette date
    prix_m2_min: Optional[int] = None      # bornes de prix_m2_local appliquées
    prix_m2_max: Optional[int] = None
    classes: List[PrixDpeLigne]
    ecart: Optional[EcartPrix] = None      # absent si l'accès est verrouillé et qu'un des deux groupes est sous le seuil


# ============================================================================
# Profil du parc
# ============================================================================

class ParcPeriodeLigne(BaseModel):
    periode_construction: Optional[str] = None
    etiquette: str
    nb_dpe: int


class ParcEnergieLigne(BaseModel):
    energie_chauffage: str
    etiquette: str
    nb_dpe: int


class DeperditionLigne(BaseModel):
    periode_construction: Optional[str] = None
    poste: str                   # murs, baies_vitrees, plancher_bas, plancher_haut, ponts_thermiques, portes
    nb_logements: int
    part_moyenne: Optional[float] = None


class ParcResponse(BaseModel):
    periodes: List[ParcPeriodeLigne]
    energies: List[ParcEnergieLigne]
    deperditions: List[DeperditionLigne]
    nb_dpe: int                  # DPE retenus
    nb_logements_deperditions: int  # parmi eux, logements dont les 6 postes de déperdition sont renseignés


# ============================================================================
# Sources et qualité
# ============================================================================

class SourceLigne(BaseModel):
    source: str
    millesime: str
    couverture: Optional[str] = None


class EntonnoirLigne(BaseModel):
    etape: int
    libelle: str
    nb_dpe: int


class GeocodageLigne(BaseModel):
    fiabilite: str
    appariement: str
    nb_liens: int


class SourcesResponse(BaseModel):
    sources: List[SourceLigne]
    entonnoir: List[EntonnoirLigne]
    geocodage: List[GeocodageLigne]
    date_maj: Optional[str] = None
