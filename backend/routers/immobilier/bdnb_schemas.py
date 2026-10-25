from typing import Dict, List, Optional

from pydantic import BaseModel


# ============================================================================
# Statistiques (bandeau)
# ============================================================================

class BdnbStatsResponse(BaseModel):
    nb_batiments: int
    nb_dpe: int                  # DPE retenus (arrêté 2021, logement, 3cl, surface > 0)
    nb_adresses: int
    nb_transactions: int         # ventes de logement du cube d'analyse (DVF Etalab, prix dans les bornes)
    trimestre_min: Optional[str] = None   # plage de trimestres de ces ventes (AAAA-Tn)
    trimestre_max: Optional[str] = None
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
    trimestre_min: Optional[str] = None    # plage de trimestres des ventes (AAAA-Tn)
    trimestre_max: Optional[str] = None
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
    
    
class QualiteMethode(BaseModel):
    methode: str                 # concordent, parcelle seule, adresse seule, divergent, croisee, ambigue, aucune
    nb_ventes: int               # ventes de contrôle retrouvées par cette méthode
    nb_ok: int                   # bâtiment retenu = bâtiment de la BDNB
    nb_erreur: int
    precision_pct: Optional[float] = None   # ok / (ok + erreur) x 100, arrondi à 0,1 ; absent si aucun rattachement retenu


class QualiteRattachement(BaseModel):
    livraison: str               # livraison DVF Etalab contrôlée
    nb_controle: int             # ventes représentatives de la BDNB retrouvées (date et prix)
    nb_ok: int
    nb_erreur: int
    precision_pct: Optional[float] = None
    methodes: List[QualiteMethode]


class SourcesResponse(BaseModel):
    sources: List[SourceLigne]
    entonnoir: List[EntonnoirLigne]
    geocodage: List[GeocodageLigne]
    qualite: Optional[QualiteRattachement] = None
    date_maj: Optional[str] = None


# ============================================================================
# Analyse (cube ventes / DPE)
# ============================================================================

class AnalyseCellule(BaseModel):
    modalites: List[str]         # une modalité par axe, dans l'ordre des axes demandés
    n: int                       # ventes ou DPE du groupe
    mediane: Optional[int] = None   # ventes : prix au m² (€), médiane et quartiles des prix fusionnés
    q1: Optional[int] = None
    q3: Optional[int] = None
    part_pct: Optional[float] = None  # DPE : part du groupe, dans les groupes affichés (par modalité du 1er axe si 2 axes)


class AnalyseMeta(BaseModel):
    source: str                  # ventes | dpe
    axes: List[str]
    seuil_applique: bool         # vrai si l'accès est verrouillé : groupes de moins de `seuil` observations retirés
    seuil: int
    nb_masquees: int
    prix_m2_min: Optional[int] = None   # ventes : bornes de prix appliquées
    prix_m2_max: Optional[int] = None
    trimestre_min: Optional[str] = None  # plage de trimestres couverte par le cube
    trimestre_max: Optional[str] = None
    date_maj: Optional[str] = None
    recouvrement_typologie: Optional[float] = None  # DPE, si l'axe ou un filtre porte sur les pièces : % de DPE avec typologie
    modalites: Dict[str, List[str]]  # valeurs présentes dans le cube par dimension de la source, hors filtres (valeurs de filtre valides)


class AnalyseResponse(BaseModel):
    meta: AnalyseMeta
    cellules: List[AnalyseCellule]


# ============================================================================
# Loyers (cube ventes avec loyers de référence)
# ============================================================================

class LoyersCellule(BaseModel):
    modalites: List[str]         # une modalité par axe, dans l'ordre des axes demandés
    n: int                       # ventes du groupe
    prix_m2_median: Optional[int] = None
    loyer_reference: Optional[float] = None   # €/m² par mois, médiane pondérée par les ventes (valeur centrale)
    loyer_majore: Optional[float] = None
    loyer_minore: Optional[float] = None
    rendement_reference_pct: Optional[float] = None   # loyer de référence x surface x 12 / prix, médiane en %
    rendement_majore_pct: Optional[float] = None      # idem avec le loyer majoré (borne haute)
    part_epoque_ambigue_pct: float       # ventes dont l'époque de construction est ambiguë (parc ancien)
    part_periode_heterogene_pct: float   # ventes dont les DPE du bâtiment divergent sur la période de construction


class LoyersMeta(BaseModel):
    axes: List[str]
    meuble: bool                 # statut meublé des loyers et rendements (chaque vente existe dans les deux statuts)
    seuil_applique: bool         # vrai si l'accès est verrouillé : groupes de moins de `seuil` ventes retirés
    seuil: int
    nb_masquees: int
    prix_m2_min: int             # bornes de prix appliquées
    prix_m2_max: int
    trimestre_min: Optional[str] = None  # plage de trimestres des ventes
    trimestre_max: Optional[str] = None
    annees_loyer: List[int]      # millésimes de loyers utilisés (le dernier arrêté disponible s'applique aux ventes plus récentes)
    source_loyers: str
    licence_loyers: str
    date_maj: Optional[str] = None
    modalites: Dict[str, List[str]]  # valeurs présentes dans le cube par dimension, hors filtres


class LoyersResponse(BaseModel):
    meta: LoyersMeta
    cellules: List[LoyersCellule]
