const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ─────────────────────────────────────────
// Types
// ─────────────────────────────────────────

export interface BeelixStats {
  periode_debut: string | null;
  periode_fin: string | null;
  total_offres: number;
  offres_cibles: number;
  comptes_cibles: number;
  offres_concurrence: number;
  nb_concurrents: number;
  total_news: number;
  charge_le: string | null;
}

export interface SecteurItem {
  secteur: string;
  libelle: string;
  nb_offres: number;
  nb_entreprises: number;
  cible: boolean;
}

export interface CompteItem {
  entreprise_nom: string;
  entreprise_normalise: string;
  secteur: string;
  secteur_libelle: string;
  naf_libelle: string | null;
  nb_offres: number;
  derniere_offre: string | null;
  titres_recents: string[];
}

export interface ComptesResponse {
  secteur: string | null;
  total: number;
  items: CompteItem[];
}

export interface OffreItem {
  id_unique: string;
  titre: string | null;
  entreprise_nom: string | null;
  secteur_libelle: string | null;
  localisation_libelle: string | null;
  type_contrat_libelle: string | null;
  date: string | null;
  url: string | null;
}

export interface OffresResponse {
  total: number;
  items: OffreItem[];
}

export interface ConcurrentItem {
  rang: number;
  entreprise_nom: string;
  nb_offres: number;
  part: number;
  est_beelix: boolean;
}

export interface ConcurrenceResponse {
  total_offres: number;
  nb_concurrents: number;
  rang_beelix: number | null;
  items: ConcurrentItem[];
}

export interface BesoinItem {
  famille: string;
  nb_offres: number;
  part: number;
}

export interface BesoinsResponse {
  secteur: string | null;
  total: number;
  items: BesoinItem[];
}

export interface TendancePoint {
  semaine: string;
  offres_cibles: number;
  offres_concurrence: number;
}

export interface NewsItem {
  id: string;
  title: string;
  date: string | null;
  source: string | null;
  url: string | null;
}

export interface NewsResponse {
  total: number;
  items: NewsItem[];
}

export interface RagSource {
  id: string;
  source: string;
  title: string;
  url: string | null;
  score: number | null;
  date?: string | null;
  entreprise?: string | null;
  secteur?: string | null;
}

export interface RagResponse {
  answer: string;
  sources: RagSource[];
  model_used: string;
  tokens_used: number;
}

// ─────────────────────────────────────────
// Fetch helpers
// ─────────────────────────────────────────

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API error ${res.status}: ${err}`);
  }
  return res.json();
}

function query(params: Record<string, string | number | undefined | null>): string {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') q.set(k, String(v));
  });
  const s = q.toString();
  return s ? `?${s}` : '';
}

// ─────────────────────────────────────────
// API calls
// ─────────────────────────────────────────

export const fetchBeelixStats = () => apiFetch<BeelixStats>('/beelix/stats');

export const fetchBeelixSecteurs = () =>
  apiFetch<{ items: SecteurItem[] }>('/beelix/secteurs');

export const fetchBeelixComptes = (secteur?: string, limit = 30) =>
  apiFetch<ComptesResponse>(`/beelix/comptes${query({ secteur, limit })}`);

export const fetchBeelixOffres = (p: { secteur?: string; entreprise?: string; limit?: number; offset?: number }) =>
  apiFetch<OffresResponse>(`/beelix/offres${query(p)}`);

export const fetchBeelixConcurrence = (limit = 20) =>
  apiFetch<ConcurrenceResponse>(`/beelix/concurrence${query({ limit })}`);

export const fetchBeelixBesoins = (secteur?: string) =>
  apiFetch<BesoinsResponse>(`/beelix/besoins${query({ secteur })}`);

export const fetchBeelixTendance = () =>
  apiFetch<{ points: TendancePoint[] }>('/beelix/tendance');

export const fetchBeelixNews = (limit = 20) =>
  apiFetch<NewsResponse>(`/beelix/news${query({ limit })}`);

export const fetchBeelixRag = (question: string, nResults = 8) =>
  apiFetch<RagResponse>('/beelix/rag', {
    method: 'POST',
    body: JSON.stringify({ question, n_results: nResults }),
  });
