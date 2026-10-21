import { request } from '@/lib/api';

// ============================================================================
// Types : miroir de backend/routers/immobilier/schemas.py
// ============================================================================

export const ETIQUETTES = ['A', 'B', 'C', 'D', 'E', 'F', 'G'] as const;
export type EtiquetteDpe = (typeof ETIQUETTES)[number];
export type Chauffage = 'electrique' | 'autre';
export type TypeLocal = 'Appartement' | 'Maison';
export type LectureChangement = 'recalcul_2026_probable' | 'refait';

export interface ImmobilierStatsResponse {
  nb_dpe: number;
  nb_passoires: number;          // étiquettes F et G
  nb_remplacants: number;        // DPE qui en remplacent un autre
  nb_ventes: number;
  date_maj_dpe: string | null;
  date_maj_dvf: string | null;
}

export interface DpeLigne {
  arrondissement: number | null;
  etiquette_dpe: EtiquetteDpe;
  flag_chauffage_electrique: boolean;
  nb_dpe: number;
  nb_remplacants: number;
}

export interface DpeResponse {
  lignes: DpeLigne[];
}

export interface PrixLigne {
  arrondissement: number | null;
  annee: number | null;
  type_local: TypeLocal;
  nb_ventes: number;
  prix_m2_median: number | null;
}

export interface PrixParisLigne {
  annee: number | null;
  type_local: TypeLocal;
  nb_ventes: number;
  prix_m2_median: number | null;
}

export interface PrixResponse {
  seuil_applique: boolean;       // vrai si l'accès est verrouillé : cellules sous `seuil` ventes retirées
  seuil: number;
  nb_masquees: number;
  lignes: PrixLigne[];
  paris: PrixParisLigne[];       // prix médian de Paris entier (toutes les ventes), par année et type
}

export interface ChangementLigne {
  numero_dpe: string;
  date_etablissement_dpe: string | null;
  adresse_ban: string | null;
  arrondissement: number | null;
  etiquette_dpe: EtiquetteDpe;
  type_energie_principale_chauffage: string | null;
  flag_chauffage_electrique: boolean;
  flag_post_reforme_2026: boolean;
  lecture: LectureChangement;
}

export interface ChangementsResponse {
  total: number;
  page: number;
  nb_pages: number;
  taille: number;
  nb_recalcul_probable: number;
  lignes: ChangementLigne[];
}

export interface ChangementsFiltres {
  page: number;
  taille: number;
  arrondissement?: number;
  etiquette?: EtiquetteDpe;
  chauffage?: Chauffage;
  postReforme?: boolean;
  dateMin?: string;              // AAAA-MM-JJ
  dateMax?: string;
}

// ============================================================================
// Appels (via le proxy /backend : le cookie d'accès est first-party)
// ============================================================================

// Public
export async function getImmobilierStats(): Promise<ImmobilierStatsResponse> {
  return request<ImmobilierStatsResponse>('/immobilier/stats');
}

// Public : table agrégée entière (quelques centaines de lignes), filtrée côté vue
export async function getDpe(): Promise<DpeResponse> {
  return request<DpeResponse>('/immobilier/dpe');
}

// Public : si l'accès est verrouillé, les cellules de moins de `seuil` ventes sont retirées par le backend
export async function getPrix(): Promise<PrixResponse> {
  return request<PrixResponse>('/immobilier/prix');
}

// Privé
export async function getChangements(filtres: ChangementsFiltres): Promise<ChangementsResponse> {
  const p = new URLSearchParams({
    page: String(filtres.page),
    taille: String(filtres.taille),
  });
  if (filtres.arrondissement) p.set('arrondissement', String(filtres.arrondissement));
  if (filtres.etiquette) p.set('etiquette', filtres.etiquette);
  if (filtres.chauffage) p.set('chauffage', filtres.chauffage);
  if (filtres.postReforme !== undefined) p.set('post_reforme', String(filtres.postReforme));
  if (filtres.dateMin) p.set('date_min', filtres.dateMin);
  if (filtres.dateMax) p.set('date_max', filtres.dateMax);
  return request<ChangementsResponse>(`/immobilier/changements?${p.toString()}`);
}
