from typing import Dict, List, Optional

from pydantic import BaseModel


# ============================================================================
# Paramètres (période)
# ============================================================================

class ParametresResponse(BaseModel):
    livraison: str                        # livraison DVF Etalab lue
    code_departement: str
    date_debut: str                       # début paramétré de la période (AAAA-MM-JJ), commun à toutes les tables
    date_fin: Optional[str] = None        # fin paramétrée ; absente = jusqu'aux dernières données
    premiere_vente: str                   # période réellement couverte par les ventes
    derniere_vente: str
    date_maj: Optional[str] = None


# ============================================================================
# Sources
# ============================================================================

class SourceLigne(BaseModel):
    source: str
    editeur: Optional[str] = None
    version: Optional[str] = None         # livraison ou millésime
    publiee: Optional[str] = None         # date de publication de la source, texte
    utilisee_par: Optional[str] = None    # parties du site qui l'utilisent
    limites: Optional[str] = None
    couverture: Optional[str] = None      # texte : « du ... au ... » ou « arrêtés ... »
    periode_debut: Optional[str] = None
    periode_fin: Optional[str] = None
    nb_lignes: Optional[int] = None       # lignes de la table lue, toutes périodes confondues
    chargee_le: Optional[str] = None      # date de dernière modification de la table (UTC)
    utilisee_depuis: Optional[str] = None # début de la période paramétrée, si elle s'applique à cette source
    statut: str                           # chargée, non chargée, consultée à la demande, reprise de la BDNB


class SourcesResponse(BaseModel):
    sources: List[SourceLigne]
    date_maj: Optional[str] = None


# ============================================================================
# Qualité
# ============================================================================

class QualiteLigne(BaseModel):
    partie: str
    indicateur: str
    valeur: Optional[float] = None
    unite: str
    commentaire: Optional[str] = None


class QualiteResponse(BaseModel):
    indicateurs: List[QualiteLigne]
    date_maj: Optional[str] = None


# ============================================================================
# Analyse (cubes du registre immobilier_org_cubes.py)
# ============================================================================

class AnalyseCellule(BaseModel):
    modalites: List[str]                  # une modalité par axe, dans l'ordre des axes demandés
    n: int                                # ventes, DPE ou immeubles du groupe
    mediane: Optional[int] = None         # cubes de prix : prix au m² (€), médiane et quartiles des prix fusionnés
    q1: Optional[int] = None
    q3: Optional[int] = None
    part_pct: Optional[float] = None      # cubes de comptage : part du groupe, dans les groupes affichés
    nb_logements: Optional[int] = None    # cube bâtiment : logements des immeubles du groupe
    nb_remplacants: Optional[int] = None  # cube DPE : DPE du groupe qui en remplacent un autre


class AnalyseMeta(BaseModel):
    cube: str
    mesure: str                           # prix | comptage
    axes: List[str]
    seuil_applique: bool                  # vrai si l'accès est verrouillé : groupes de moins de `seuil` observations retirés
    seuil: int
    nb_masquees: int
    prix_m2_min: Optional[int] = None     # cubes de prix : bornes appliquées
    prix_m2_max: Optional[int] = None
    mois_min: Optional[str] = None        # plage de mois couverte par le cube (AAAA-MM), si le cube a une dimension mois
    mois_max: Optional[str] = None
    date_maj: Optional[str] = None
    recouvrement_typologie: Optional[float] = None  # cube croise_dpe, si l'axe ou un filtre porte sur les pièces
    modalites: Dict[str, List[str]]       # valeurs présentes dans le cube par dimension, hors filtres (valeurs de filtre valides)


class AnalyseResponse(BaseModel):
    meta: AnalyseMeta
    cellules: List[AnalyseCellule]


# ============================================================================
# Loyers (cube des ventes avec loyers de référence)
# ============================================================================

class LoyersCellule(BaseModel):
    modalites: List[str]                  # une modalité par axe, dans l'ordre des axes demandés
    n: int                                # ventes du groupe
    prix_m2_median: Optional[int] = None
    loyer_reference: Optional[float] = None   # €/m² par mois, médiane pondérée par les ventes (valeur centrale)
    loyer_majore: Optional[float] = None
    loyer_minore: Optional[float] = None
    rendement_reference_pct: Optional[float] = None   # loyer de référence x surface x 12 / prix, médiane en %
    rendement_majore_pct: Optional[float] = None      # idem avec le loyer majoré (borne haute)
    part_epoque_ambigue_pct: float        # ventes dont l'époque de construction est ambiguë (parc ancien)
    part_periode_heterogene_pct: float    # ventes dont les DPE du bâtiment divergent sur la période de construction


class LoyersMeta(BaseModel):
    axes: List[str]
    meuble: bool                          # statut meublé des loyers et rendements (chaque vente existe dans les deux statuts)
    seuil_applique: bool                  # vrai si l'accès est verrouillé : groupes de moins de `seuil` ventes retirés
    seuil: int
    nb_masquees: int
    prix_m2_min: int                      # bornes de prix appliquées
    prix_m2_max: int
    mois_min: Optional[str] = None        # plage de mois des ventes (AAAA-MM)
    mois_max: Optional[str] = None
    annees_loyer: List[int]               # millésimes de loyers utilisés
    source_loyers: str
    licence_loyers: str
    date_maj: Optional[str] = None
    modalites: Dict[str, List[str]]       # valeurs présentes dans le cube par dimension, hors filtres


class LoyersResponse(BaseModel):
    meta: LoyersMeta
    cellules: List[LoyersCellule]


# ============================================================================
# Prix et performance énergétique (écart des passoires)
# ============================================================================

class PrixDpeLigne(BaseModel):
    classe_dpe: str                       # classe médiane des DPE du bâtiment
    nb_ventes: int
    prix_m2_median: Optional[float] = None


class EcartPrix(BaseModel):
    nb_fg: int
    prix_m2_median_fg: Optional[float] = None
    nb_d: int
    prix_m2_median_d: Optional[float] = None
    ecart_pct: Optional[float] = None     # (médiane F+G / médiane D - 1) x 100, arrondi à 0,1 ; brut, non corrigé


class PrixDpeResponse(BaseModel):
    seuil_applique: bool                  # vrai si l'accès est verrouillé : classes de moins de `seuil` ventes retirées
    seuil: int
    nb_masquees: int
    mois_min: Optional[str] = None        # plage de mois des ventes (AAAA-MM)
    mois_max: Optional[str] = None
    prix_m2_min: Optional[int] = None
    prix_m2_max: Optional[int] = None
    classes: List[PrixDpeLigne]
    ecart: Optional[EcartPrix] = None     # absent si l'accès est verrouillé et qu'un des deux groupes est sous le seuil
