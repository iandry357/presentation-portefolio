import { request } from '@/lib/api';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ─────────────────────────────────────────
// Types
// ─────────────────────────────────────────

export interface SectionCount {
  section: string;
  langue: string | null;
  nb_documents: number;
}

export interface WavestoneStats {
  total_documents: number;
  sections: SectionCount[];
  last_updated: string | null;
  total_offres: number;
  intitules_distincts: number;
  periode_debut: string | null;
  periode_fin: string | null;
  charge_le: string | null;
}

export interface NewsItem {
  id: string;
  title: string;
  date: string | null;
  source: string | null;
  url: string | null;
  section: string;
  langue: string | null;
  source_name: string | null;
  date_type: string | null;
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
  section?: string | null;
  langue?: string | null;
}

export interface RagResponse {
  answer: string;
  sources: RagSource[];
  model_used: string;
  tokens_used: number;
}

export interface Topic {
  topic_id: number;
  label: string;
  keywords: string[];
  lang: string | null;
  summary: string | null;
}

export interface TopicDoc {
  id: string | null;
  source: string | null;
  title: string | null;
  date: string | null;
  url: string | null;
  lang: string | null;
  section: string | null;
  dominant_topic: number;
  dominant_label: string;
  confidence: number;
}

export interface TopicModelingResponse {
  n_topics: number;
  total_docs: number;
  topics: Topic[];
  docs: TopicDoc[];
}

export interface PosteItem {
  titre: string;
  famille: string;
  nb_publications: number;
  premiere_date: string | null;
  derniere_date: string | null;
  lieu: string | null;
  contrat: string | null;
  source: string | null;
  url: string | null;
  score_max: number | null;
  categorie: string | null;
  cible_intitule: string | null;
  a_texte_complet: boolean;
}

export interface FamilleItem {
  famille: string;
  nb_intitules: number;
  nb_publications: number;
}

export interface RecrutementResponse {
  total_offres: number;
  intitules_distincts: number;
  periode_debut: string | null;
  periode_fin: string | null;
  familles: FamilleItem[];
  postes: PosteItem[];
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

export const fetchWavestoneStats = () => apiFetch<WavestoneStats>('/wavestone/stats');

export const fetchWavestoneNews = (p: { langue?: string; section?: string; limit?: number; offset?: number }) =>
  apiFetch<NewsResponse>(`/wavestone/news${query(p)}`);

// Routes à accès privé : via le proxy /backend (cookie d'accès first-party)
export const fetchWavestoneRag = (question: string, nResults = 8) =>
  request<RagResponse>('/wavestone/rag', {
    method: 'POST',
    body: { question, n_results: nResults },
  });

export const fetchWavestoneTopicModeling = () =>
  apiFetch<TopicModelingResponse>('/wavestone/ml/topic-modeling');

export const fetchWavestoneRecrutement = () =>
  request<RecrutementResponse>('/wavestone/recrutement');
