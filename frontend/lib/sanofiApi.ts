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

// ML
// export interface ClusterItem {
//   cluster_id: number;
//   label: string;
//   avg_duration_months: number;
//   trial_count: number;
// }
export interface ClusterItem {
  cluster_id: number;
  label: string;
  count: number;
  keywords: string[];
}

export interface DurationClusterItem {
  cluster_id: number;
  label: string;
  avg_duration_months: number;
  trial_count: number;
}

export interface ClusteringResponse {
  total_trials: number;
  n_clusters: number;
  clusters: ClusterItem[];
  // trials: { id: string; title: string; cluster_id: number; dominant_label: string }[];
  trials: {
    id: string;
    title: string;
    cluster_id: number;
    phase: string;
    status: string;
    conditions: string[];
  }[];
}

export interface BayesianForecast {
  already_observed: number | null;
  predicted_remaining: number | null;
  total_predicted: number | null;
  total_ci_lower: number | null;
  total_ci_upper: number | null;
  months_remaining: number | null;
  n_years_used: number | null;
  avg_monthly_rate: number | null;
}

export interface ForecastingResponse {
  total_trials: number;
  volume_by_year: { year: number; count: number }[];
  phases_by_year: { year: number; phases: Record<string, number> }[];
  duration_by_cluster: DurationClusterItem[];
  bayesian_forecast?: BayesianForecast;
}

export interface TopicItem {
  topic_id: number;
  label: string;
  keywords: string[];
}

export interface TopicModelingResponse {
  n_topics: number;
  total_docs: number;
  sources: { press_releases: number; google_news: number };
  topics: TopicItem[];
  // docs: { id: string; source: string; title: string; date: string; url?: string; dominant_topic: number; dominant_label: string; confidence: number }[];
  docs: { 
    id: string; 
    source: string; 
    title: string; 
    date: string; 
    url?: string;
    dominant_topic: number; 
    dominant_label: string; 
    confidence: number 
  }[];
}

export async function fetchClustering(): Promise<ClusteringResponse> {
  return apiFetch<ClusteringResponse>('/sanofi/ml/clustering');
}

export async function fetchForecasting(): Promise<ForecastingResponse> {
  return apiFetch<ForecastingResponse>('/sanofi/ml/forecasting');
}

export async function fetchTopicModeling(): Promise<TopicModelingResponse> {
  return apiFetch<TopicModelingResponse>('/sanofi/ml/topic-modeling');
}

export interface PressReleaseItem {
  id: string;
  title: string;
  date: string | null;
  source_name: string | null;
  url: string | null;
}

export interface PressReleasesResponse {
  total: number;
  items: PressReleaseItem[];
}

export async function fetchPressReleases(params?: {
  limit?: number;
}): Promise<PressReleasesResponse> {
  const q = new URLSearchParams();
  if (params?.limit) q.set('limit', String(params.limit));
  return apiFetch<PressReleasesResponse>(`/sanofi/press-releases?${q}`);
}