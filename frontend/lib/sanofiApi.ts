const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ─────────────────────────────────────────
// Types
// ─────────────────────────────────────────

export interface SanofiStats {
  total_clinical_trials: number;
  total_pubmed: number;
  total_news: number;
  last_updated: string | null;
}

export interface ClinicalTrialItem {
  id: string;
  title: string;
  date: string | null;
  phase: string | null;
  status: string | null;
  conditions: string[];
  study_type: string | null;
  sponsor: string | null;
  url: string | null;
}

export interface ClinicalTrialsResponse {
  total: number;
  items: ClinicalTrialItem[];
}

export interface PubMedItem {
  id: string;
  title: string;
  date: string | null;
  journal: string | null;
  authors: string[];
  keywords: string[];
  url: string | null;
}

export interface PubMedResponse {
  total: number;
  items: PubMedItem[];
}

export interface NewsItem {
  id: string;
  title: string;
  date: string | null;
  source_name: string | null;
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
}

export interface RagResponse {
  answer: string;
  sources: RagSource[];
  model_used: string;
  tokens_used: number;
}

export interface SearchResult {
  id: string;
  source: string;
  title: string;
  date: string | null;
  url: string | null;
  score: number | null;
  excerpt: string | null;
}

export interface SearchResponse {
  total: number;
  results: SearchResult[];
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

// ─────────────────────────────────────────
// API calls
// ─────────────────────────────────────────

export async function fetchSanofiStats(): Promise<SanofiStats> {
  return apiFetch<SanofiStats>('/sanofi/stats');
}

export async function fetchClinicalTrials(params?: {
  limit?: number;
  status?: string;
  phase?: string;
}): Promise<ClinicalTrialsResponse> {
  const q = new URLSearchParams();
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.status) q.set('status', params.status);
  if (params?.phase) q.set('phase', params.phase);
  return apiFetch<ClinicalTrialsResponse>(`/sanofi/clinical-trials?${q}`);
}

export async function fetchPubMed(params?: {
  limit?: number;
}): Promise<PubMedResponse> {
  const q = new URLSearchParams();
  if (params?.limit) q.set('limit', String(params.limit));
  return apiFetch<PubMedResponse>(`/sanofi/pubmed?${q}`);
}

export async function fetchNews(params?: {
  limit?: number;
}): Promise<NewsResponse> {
  const q = new URLSearchParams();
  if (params?.limit) q.set('limit', String(params.limit));
  return apiFetch<NewsResponse>(`/sanofi/news?${q}`);
}

export async function fetchRag(
  question: string,
  sources?: string[],
  nResults?: number
): Promise<RagResponse> {
  return apiFetch<RagResponse>('/sanofi/rag', {
    method: 'POST',
    body: JSON.stringify({
      question,
      sources: sources ?? null,
      n_results: nResults ?? 5,
    }),
  });
}

export async function fetchSearch(
  query: string,
  sources?: string[],
  nResults?: number
): Promise<SearchResponse> {
  const q = new URLSearchParams();
  q.set('query', query);
  if (nResults) q.set('n_results', String(nResults));
  if (sources?.length) sources.forEach(s => q.append('sources', s));
  return apiFetch<SearchResponse>(`/sanofi/search?${q}`);
}