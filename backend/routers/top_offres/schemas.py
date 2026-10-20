from datetime import datetime
from typing import Dict, List, Literal, Optional


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
    liste: Literal["a_lire", "zone_grise", "masque"]
    motif_masque: Optional[str] = None   # filtre dur (stage, alternance...) ou score_bas ; null hors masque
    secteur: Optional[str] = None
    # Type affiché : la correction de l'utilisateur si elle existe, sinon l'automatique du mart
    type_entreprise: str
    type_entreprise_corrige: bool = False
    entreprise_exclue: bool = False


class TopCompteurs(BaseModel):
    a_lire: int
    zone_grise: int
    masque: int


class TopResponse(BaseModel):
    """Une page d'une liste (onglet), avec les compteurs des trois listes pour les libellés d'onglets."""
    jours: int
    liste: Literal["a_lire", "zone_grise", "masque"]
    page: int                     # page servie (ramenée à la dernière si la demande la dépasse)
    nb_pages: int
    taille: int                   # offres par page
    total: int                    # offres de la liste après filtres, avant découpe
    offres: List[TopOffre]
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
    # Intitulés des cibles validées, par cible_id (libellés des graphiques) ; vide si indisponible
    cibles: Dict[str, str] = {}


# ============================================================================
# Entreprises (agrégat des offres scorées)
# ============================================================================

class EntrepriseStat(BaseModel):
    """Une entreprise : volume et adéquation de ses offres scorées sur la période."""
    entreprise_normalise: str
    entreprise_nom: Optional[str] = None
    secteur: Optional[str] = None
    naf_libelle: Optional[str] = None
    # Type affiché : la correction de l'utilisateur si elle existe, sinon l'automatique du mart
    type_entreprise: str
    type_entreprise_corrige: bool = False
    entreprise_exclue: bool = False
    nb_offres: int
    nb_coeur: int
    nb_adjacent: int
    nb_hors_cible: int
    nb_a_lire: int
    nb_zone_grise: int
    score_max: Optional[int] = None
    score_moyen: Optional[float] = None
    derniere_offre: Optional[str] = None


class EntreprisesResponse(BaseModel):
    jours: int
    total: int                    # entreprises correspondant aux filtres, avant la limite
    entreprises: List[EntrepriseStat]
    secteurs: List[str]           # secteurs présents sur la période (options du filtre)


class OffreEntreprise(BaseModel):
    """Une offre scorée d'une entreprise (liste : a_lire, zone_grise ou masque)."""
    id_unique: str
    source: Optional[str] = None
    titre: str
    localisation_libelle: Optional[str] = None
    type_contrat_libelle: Optional[str] = None
    salaire_libelle: Optional[str] = None
    url_offre: Optional[str] = None
    date_publication: Optional[str] = None
    date_collecte: Optional[str] = None
    score: Optional[int] = None
    categorie: Optional[str] = None
    liste: str
    raison: Optional[str] = None


class OffresEntrepriseResponse(BaseModel):
    entreprise_normalise: str
    jours: int
    offres: List[OffreEntreprise]

# ============================================================================
# Décisions « intéressé / pas intéressé »
# ============================================================================

class DecisionCreate(BaseModel):
    """
    « pas_interesse » et « expire » : enregistrent la décision (l'offre sort du top).
    « interesse » : crée un brouillon dans job_offers, après contrôle de doublon.
    Un doublon détecté n'est jamais bloquant : confirmer=True crée quand même le brouillon,
    utiliser_job_offer_id rattache la décision à une offre déjà présente dans job_offers.
    """
    id_unique: str = Field(..., min_length=1)
    decision: Literal["pas_interesse", "interesse", "expire"]
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
