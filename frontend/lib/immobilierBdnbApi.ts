import { request } from '@/lib/api';

// ============================================================================
// Types : miroir de backend/routers/immobilier/bdnb_schemas.py
// ============================================================================

export interface BdnbStatsResponse {
  nb_batiments: number;
  nb_dpe: number;                // DPE retenus (arrêté 2021, logement, 3cl, surface > 0)
  nb_adresses: number;
  nb_transactions: number;       // transactions DVF représentatives (une par bâtiment)
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
  date_vente_min: string | null; // ventes retenues depuis cette date (AAAA-MM-JJ)
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

export interface SourcesResponse {
  sources: SourceLigne[];
  entonnoir: EntonnoirLigne[];
  geocodage: GeocodageLigne[];
  date_maj: string | null;
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
