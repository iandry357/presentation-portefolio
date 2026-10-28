import { request } from '@/lib/api';

// ============================================================================
// Types : miroir de backend/routers/immobilier/org_schemas.py
// ============================================================================

export interface OrgParametres {
  livraison: string;             // livraison DVF Etalab lue
  code_departement: string;
  date_debut: string;            // début paramétré de la période (AAAA-MM-JJ), commun à toutes les parties
  date_fin: string | null;       // absente : jusqu'aux dernières données
  premiere_vente: string;        // période réellement couverte par les ventes
  derniere_vente: string;
  date_maj: string | null;
}

export interface OrgSource {
  source: string;
  editeur: string | null;
  version: string | null;
  publiee: string | null;
  utilisee_par: string | null;
  limites: string | null;
  couverture: string | null;     // « du ... au ... » ou « arrêtés ... »
  periode_debut: string | null;
  periode_fin: string | null;
  nb_lignes: number | null;
  chargee_le: string | null;
  utilisee_depuis: string | null;
  statut: string;                // chargée, non chargée, consultée à la demande, reprise de la BDNB
}

export interface OrgSourcesResponse {
  sources: OrgSource[];
  date_maj: string | null;
}

export interface OrgQualiteLigne {
  partie: string;
  indicateur: string;
  valeur: number | null;
  unite: string;
  commentaire: string | null;
}

export interface OrgQualiteResponse {
  indicateurs: OrgQualiteLigne[];
  date_maj: string | null;
}

// Analyse (cubes du registre immobilier_org_cubes.py)
export type CubeOrg = 'dvf' | 'dpe' | 'batiment' | 'croise_ventes' | 'croise_dpe';
export type FiltresOrg = Record<string, string[]>;   // dimension -> valeurs (OU au sein d'une dimension)

export interface OrgAnalyseCellule {
  modalites: string[];           // une modalité par axe, dans l'ordre des axes demandés
  n: number;                     // ventes, DPE ou immeubles du groupe
  mediane: number | null;        // cubes de prix : prix au m² (€)
  q1: number | null;
  q3: number | null;
  part_pct: number | null;       // cubes de comptage : part du groupe, dans les groupes affichés
  nb_logements: number | null;   // cube bâtiment
  nb_remplacants: number | null; // cube DPE
}

export interface OrgAnalyseMeta {
  cube: CubeOrg;
  mesure: 'prix' | 'comptage';
  axes: string[];
  seuil_applique: boolean;       // vrai si l'accès est verrouillé : groupes sous `seuil` observations retirés
  seuil: number;
  nb_masquees: number;
  prix_m2_min: number | null;
  prix_m2_max: number | null;
  mois_min: string | null;       // plage de mois du cube (AAAA-MM)
  mois_max: string | null;
  date_maj: string | null;
  recouvrement_typologie: number | null;
  modalites: Record<string, string[]>;   // valeurs présentes par dimension, hors filtres
}

export interface OrgAnalyseResponse {
  meta: OrgAnalyseMeta;
  cellules: OrgAnalyseCellule[];
}

// Loyers
export type DimensionLoyersOrg = 'mois' | 'annee_loyer' | 'arrondissement' | 'pieces' | 'epoque';

export interface OrgLoyersCellule {
  modalites: string[];
  n: number;
  prix_m2_median: number | null;
  loyer_reference: number | null;      // €/m² par mois
  loyer_majore: number | null;
  loyer_minore: number | null;
  rendement_reference_pct: number | null;
  rendement_majore_pct: number | null;
  part_epoque_ambigue_pct: number;
  part_periode_heterogene_pct: number;
}

export interface OrgLoyersMeta {
  axes: DimensionLoyersOrg[];
  meuble: boolean;
  seuil_applique: boolean;
  seuil: number;
  nb_masquees: number;
  prix_m2_min: number;
  prix_m2_max: number;
  mois_min: string | null;
  mois_max: string | null;
  annees_loyer: number[];
  source_loyers: string;
  licence_loyers: string;
  date_maj: string | null;
  modalites: Record<string, string[]>;
}

export interface OrgLoyersResponse {
  meta: OrgLoyersMeta;
  cellules: OrgLoyersCellule[];
}

// Prix et performance énergétique
export interface OrgPrixDpeLigne {
  classe_dpe: string;
  nb_ventes: number;
  prix_m2_median: number | null;
}

export interface OrgEcartPrix {
  nb_fg: number;
  prix_m2_median_fg: number | null;
  nb_d: number;
  prix_m2_median_d: number | null;
  ecart_pct: number | null;      // (médiane F+G / médiane D - 1) x 100 ; brut, non corrigé
}

export interface OrgPrixDpeResponse {
  seuil_applique: boolean;
  seuil: number;
  nb_masquees: number;
  mois_min: string | null;
  mois_max: string | null;
  prix_m2_min: number | null;
  prix_m2_max: number | null;
  classes: OrgPrixDpeLigne[];
  ecart: OrgEcartPrix | null;
}

// Tableaux bruts (privé)
export type JeuBrut = 'dvf' | 'dpe' | 'batiment';
export type FormatCsv = 'excel' | 'standard';

export interface OrgBrutColonne {
  nom: string;                   // nom technique de la colonne
  libelle: string;
  description: string;
  defaut: boolean;
  sensible: boolean;             // adresse, coordonnée ou identifiant : simple marqueur d'affichage
}

export interface OrgBrutJeu {
  jeu: JeuBrut;
  libelle: string;
  source: string;
  colonne_date: string | null;   // absente : jeu sans date, la période ne s'applique pas
  colonnes: OrgBrutColonne[];
}

export interface OrgBrutCatalogue {
  plafond_lignes: number;
  lignes_apercu: number;
  formats: FormatCsv[];
  format_defaut: FormatCsv;
  date_debut_defaut: string;
  jeux: OrgBrutJeu[];
}

export interface OrgBrutApercu {
  jeu: JeuBrut;
  arrondissement: number;
  date_debut: string | null;
  date_fin: string | null;
  nb_lignes: number;
  plafond_lignes: number;
  colonnes: OrgBrutColonne[];
  lignes: Record<string, string | number | boolean | null>[];
}

export interface ParametresBrut {
  arrondissement: number;
  debut?: string;                // AAAA-MM-JJ ; absent : début de la période paramétrée
  fin?: string;
  colonnes?: string[];           // absent : colonnes par défaut
}

// ============================================================================
// Appels (via le proxy /backend : le cookie d'accès est first-party)
// ============================================================================

const API_URL = '/backend';   // proxy Next.js, comme lib/api.ts : sert aux téléchargements par lien

function ajouterFiltres(params: URLSearchParams, filtres: FiltresOrg) {
  Object.entries(filtres).forEach(([dimension, valeurs]) =>
    valeurs.forEach(valeur => params.append('filtre', `${dimension}:${valeur}`)),
  );
}

function parametresBrut({ arrondissement, debut, fin, colonnes }: ParametresBrut): URLSearchParams {
  const params = new URLSearchParams({ arrondissement: String(arrondissement) });
  if (debut) params.set('debut', debut);
  if (fin) params.set('fin', fin);
  colonnes?.forEach(colonne => params.append('colonnes', colonne));
  return params;
}

// Public
export async function getOrgParametres(): Promise<OrgParametres> {
  return request<OrgParametres>('/immobilier/org/parametres');
}

// Public
export async function getOrgSources(): Promise<OrgSourcesResponse> {
  return request<OrgSourcesResponse>('/immobilier/org/sources');
}

// Public
export async function getOrgQualite(): Promise<OrgQualiteResponse> {
  return request<OrgQualiteResponse>('/immobilier/org/qualite');
}

// Public : si l'accès est verrouillé, les groupes de moins de `seuil` observations sont retirés par le backend
export async function getOrgAnalyse(cube: CubeOrg, axes: string[], filtres: FiltresOrg): Promise<OrgAnalyseResponse> {
  const params = new URLSearchParams();
  axes.forEach(axe => params.append('axe', axe));
  ajouterFiltres(params, filtres);
  return request<OrgAnalyseResponse>(`/immobilier/org/analyse/${cube}?${params.toString()}`);
}

// Public : seuil si verrouillé ; un seul statut (meublé ou non) par requête
export async function getOrgLoyers(
  axes: DimensionLoyersOrg[],
  meuble: boolean,
  filtres: FiltresOrg,
): Promise<OrgLoyersResponse> {
  const params = new URLSearchParams({ meuble: String(meuble) });
  axes.forEach(axe => params.append('axe', axe));
  ajouterFiltres(params, filtres);
  return request<OrgLoyersResponse>(`/immobilier/org/loyers?${params.toString()}`);
}

// Public : seuil si verrouillé
export async function getOrgEcartPrix(): Promise<OrgPrixDpeResponse> {
  return request<OrgPrixDpeResponse>('/immobilier/org/ecart-prix');
}

// Privé (403 sans code)
export async function getOrgBrutCatalogue(): Promise<OrgBrutCatalogue> {
  return request<OrgBrutCatalogue>('/immobilier/org/brut/catalogue');
}

// Privé : aperçu et nombre total de lignes ; 422 si le plafond est dépassé
export async function getOrgBrutApercu(jeu: JeuBrut, parametres: ParametresBrut): Promise<OrgBrutApercu> {
  return request<OrgBrutApercu>(`/immobilier/org/brut/${jeu}?${parametresBrut(parametres).toString()}`);
}

// Privé : adresse du CSV, à ouvrir par un lien (le navigateur envoie le cookie d'accès)
export function urlExportBrut(
  jeu: JeuBrut,
  parametres: ParametresBrut,
  format: FormatCsv,
  libelles: boolean,
): string {
  const params = parametresBrut(parametres);
  params.set('format', format);
  params.set('libelles', String(libelles));
  return `${API_URL}/immobilier/org/brut/${jeu}/export?${params.toString()}`;
}
