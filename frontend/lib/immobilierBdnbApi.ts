import { request } from '@/lib/api';

// ============================================================================
// Types : miroir de backend/routers/immobilier/bdnb_schemas.py
// ============================================================================

export interface BdnbStatsResponse {
  nb_batiments: number;
  nb_dpe: number;                // DPE retenus (arrêté 2021, logement, 3cl, surface > 0)
  nb_adresses: number;
  nb_transactions: number;       // ventes de logement du cube d'analyse (DVF Etalab, prix dans les bornes)
  trimestre_min: string | null;  // plage de trimestres de ces ventes (AAAA-Tn)
  trimestre_max: string | null;
  millesime: string | null;      // millésime de la BDNB
  date_maj: string | null;
}

export interface PrixDpeLigne {
  classe_dpe: string;            // classe médiane des DPE du bâtiment
  nb_ventes: number;
  prix_m2_median: number | null;
}

export interface EcartPrix {
  nb_fg: number;
  prix_m2_median_fg: number | null;
  nb_d: number;
  prix_m2_median_d: number | null;
  ecart_pct: number | null;      // (médiane F+G / médiane D - 1) x 100 ; brut, non corrigé
}

export interface PrixDpeResponse {
  seuil_applique: boolean;       // vrai si l'accès est verrouillé : classes sous `seuil` ventes retirées
  seuil: number;
  nb_masquees: number;
  trimestre_min: string | null;  // plage de trimestres des ventes (AAAA-Tn)
  trimestre_max: string | null;
  prix_m2_min: number | null;    // bornes de prix_m2_local appliquées
  prix_m2_max: number | null;
  classes: PrixDpeLigne[];
  ecart: EcartPrix | null;       // absent si l'accès est verrouillé et qu'un des deux groupes est sous le seuil
}

export interface ParcPeriodeLigne {
  periode_construction: string | null;
  etiquette: string;
  nb_dpe: number;
}

export interface ParcEnergieLigne {
  energie_chauffage: string;
  etiquette: string;
  nb_dpe: number;
}

export interface DeperditionLigne {
  periode_construction: string | null;
  poste: string;                 // murs, baies_vitrees, plancher_bas, plancher_haut, ponts_thermiques, portes
  nb_logements: number;
  part_moyenne: number | null;
}

export interface ParcResponse {
  periodes: ParcPeriodeLigne[];
  energies: ParcEnergieLigne[];
  deperditions: DeperditionLigne[];
  nb_dpe: number;                // DPE retenus
  nb_logements_deperditions: number;  // parmi eux, logements dont les 6 postes sont renseignés
}

export interface SourceLigne {
  source: string;
  millesime: string;
  couverture: string | null;
}

export interface EntonnoirLigne {
  etape: number;
  libelle: string;
  nb_dpe: number;
}

export interface GeocodageLigne {
  fiabilite: string;
  appariement: string;
  nb_liens: number;
}

export interface QualiteMethode {
  methode: string;               // concordent, parcelle seule, adresse seule, divergent, croisee, ambigue, aucune
  nb_ventes: number;             // ventes de contrôle retrouvées par cette méthode
  nb_ok: number;
  nb_erreur: number;
  precision_pct: number | null;  // ok / (ok + erreur) ; null si aucun rattachement retenu
}

export interface QualiteRattachement {
  livraison: string;
  nb_controle: number;
  nb_ok: number;
  nb_erreur: number;
  precision_pct: number | null;
  methodes: QualiteMethode[];
}

export interface SourcesResponse {
  sources: SourceLigne[];
  entonnoir: EntonnoirLigne[];
  geocodage: GeocodageLigne[];
  qualite: QualiteRattachement | null;
  date_maj: string | null;
}

// Analyse (cube ventes / DPE)
export type SourceAnalyse = 'ventes' | 'dpe';
export type DimensionAnalyse = 'trimestre' | 'arrondissement' | 'pieces' | 'tranche_surface' | 'etiquette' | 'rattachee';
export type FiltresAnalyse = Partial<Record<DimensionAnalyse, string[]>>;

export interface AnalyseCellule {
  modalites: string[];           // une modalité par axe, dans l'ordre des axes demandés
  n: number;                     // ventes ou DPE du groupe
  mediane: number | null;        // ventes : prix au m² (€), médiane et quartiles des prix
  q1: number | null;
  q3: number | null;
  part_pct: number | null;       // DPE : part du groupe, dans les groupes affichés
}

export interface AnalyseMeta {
  source: SourceAnalyse;
  axes: DimensionAnalyse[];
  seuil_applique: boolean;       // vrai si l'accès est verrouillé : groupes sous `seuil` observations retirés
  seuil: number;
  nb_masquees: number;
  prix_m2_min: number | null;    // ventes : bornes de prix appliquées
  prix_m2_max: number | null;
  trimestre_min: string | null;  // plage de trimestres couverte par le cube
  trimestre_max: string | null;
  date_maj: string | null;
  recouvrement_typologie: number | null;  // DPE, si les pièces sont utilisées : % de DPE avec typologie
  modalites: Partial<Record<DimensionAnalyse, string[]>>;  // valeurs présentes par dimension, hors filtres
}

export interface AnalyseResponse {
  meta: AnalyseMeta;
  cellules: AnalyseCellule[];
}

// Loyers (cube ventes avec loyers de référence)
export type DimensionLoyers = 'trimestre' | 'annee_loyer' | 'arrondissement' | 'pieces' | 'epoque';
export type FiltresLoyers = Partial<Record<DimensionLoyers, string[]>>;

export interface LoyersCellule {
  modalites: string[];                 // une modalité par axe, dans l'ordre des axes demandés
  n: number;                           // ventes du groupe
  prix_m2_median: number | null;
  loyer_reference: number | null;      // €/m² par mois, médiane pondérée par les ventes (valeur centrale)
  loyer_majore: number | null;
  loyer_minore: number | null;
  rendement_reference_pct: number | null;  // loyer de référence x surface x 12 / prix, médiane en %
  rendement_majore_pct: number | null;     // idem avec le loyer majoré (borne haute)
  part_epoque_ambigue_pct: number;     // ventes dont l'époque de construction est ambiguë
  part_periode_heterogene_pct: number; // ventes dont les DPE de l'immeuble divergent sur la période
}

export interface LoyersMeta {
  axes: DimensionLoyers[];
  meuble: boolean;
  seuil_applique: boolean;             // vrai si l'accès est verrouillé : groupes sous `seuil` ventes retirés
  seuil: number;
  nb_masquees: number;
  prix_m2_min: number;
  prix_m2_max: number;
  trimestre_min: string | null;        // plage de trimestres de toutes les ventes du cube
  trimestre_max: string | null;
  annees_loyer: number[];              // arrêtés présents dans le cube
  source_loyers: string;
  licence_loyers: string;
  date_maj: string | null;
  modalites: Partial<Record<DimensionLoyers, string[]>>;  // valeurs présentes par dimension, hors filtres
}

export interface LoyersResponse {
  meta: LoyersMeta;
  cellules: LoyersCellule[];
}

// Assistant bailleur (miroir de backend/routers/immobilier/assistant_schemas.py)
export interface MessageHistorique {
  role: 'user' | 'assistant';
  content: string;
}

export interface SourceCitee {
  reference: string;             // ex. « Loi n° 89-462 du 6 juillet 1989, art. 6 »
  type_texte: string;            // loi, code, décret, arrêté, BOFiP, loi de finances
  statut: string;                // « en vigueur »
  date_version: string | null;
  url: string;
}

export interface AssistantReponse {
  reponse: string;               // citations [n] renumérotées dans l'ordre d'apparition
  sources: SourceCitee[];        // construites par le serveur depuis les métadonnées
  refus: boolean;                // vrai si aucune source du corpus ne répond
  modele: string | null;
}

// ============================================================================
// Appels (via le proxy /backend : le cookie d'accès est first-party)
// ============================================================================

// Public
export async function getBdnbStats(): Promise<BdnbStatsResponse> {
  return request<BdnbStatsResponse>('/immobilier/bdnb/stats');
}

// Public : si l'accès est verrouillé, les classes de moins de `seuil` ventes sont retirées par le backend
export async function getBdnbPrixDpe(): Promise<PrixDpeResponse> {
  return request<PrixDpeResponse>('/immobilier/bdnb/prix-dpe');
}

// Public
export async function getBdnbParc(): Promise<ParcResponse> {
  return request<ParcResponse>('/immobilier/bdnb/parc');
}

// Public
export async function getBdnbSources(): Promise<SourcesResponse> {
  return request<SourcesResponse>('/immobilier/bdnb/sources');
}

// Public : si l'accès est verrouillé, les groupes de moins de `seuil` observations sont retirés par le backend
export async function getBdnbAnalyse(
  source: SourceAnalyse,
  axes: DimensionAnalyse[],
  filtres: FiltresAnalyse,
): Promise<AnalyseResponse> {
  const params = new URLSearchParams({ source });
  axes.forEach(axe => params.append('axe', axe));
  (Object.entries(filtres) as [DimensionAnalyse, string[] | undefined][]).forEach(([dimension, valeurs]) =>
    valeurs?.forEach(valeur => params.append(dimension, valeur)),
  );
  return request<AnalyseResponse>(`/immobilier/bdnb/analyse?${params.toString()}`);
}

// Public : si l'accès est verrouillé, les groupes de moins de `seuil` ventes sont retirés par le backend
export async function getBdnbLoyers(
  axes: DimensionLoyers[],
  meuble: boolean,
  filtres: FiltresLoyers,
): Promise<LoyersResponse> {
  const params = new URLSearchParams({ meuble: String(meuble) });
  axes.forEach(axe => params.append('axe', axe));
  (Object.entries(filtres) as [DimensionLoyers, string[] | undefined][]).forEach(([dimension, valeurs]) =>
    valeurs?.forEach(valeur => params.append(dimension, valeur)),
  );
  return request<LoyersResponse>(`/immobilier/bdnb/loyers?${params.toString()}`);
}

// Assistant bailleur : public, avec limite de débit par visiteur côté backend ; les sources sont construites par le serveur
export async function postAssistantChat(question: string, historique: MessageHistorique[]): Promise<AssistantReponse> {
  return request<AssistantReponse>('/immobilier/assistant/chat', { method: 'POST', body: { question, historique } });
}
