const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ─────────────────────────────────────────
// Types — Stats & News
// ─────────────────────────────────────────

export interface BdfStats {
  total_news: number;
  last_updated: string | null;
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

// ─────────────────────────────────────────
// Types — RAG
// ─────────────────────────────────────────

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

// ─────────────────────────────────────────
// Types — Topic Modeling
// ─────────────────────────────────────────

export interface Topic {
  topic_id: number;
  label: string;
  keywords: string[];
}

export interface TopicDoc {
  id: string;
  source: string;
  title: string;
  date: string;
  url?: string;
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

// ─────────────────────────────────────────
// Types — EBA (scoring composite)
// ─────────────────────────────────────────

export interface EbaRatios {
  cet1_ratio: number;
  leverage_ratio: number;
  npl_ratio: number;
}

export interface EbaMethodology {
  description: string;
  eu_average_definition: string;
  coverage_note: string;
  unit: string;
  not_a_regulatory_score: boolean;
  not_a_trained_model: boolean;
}

export interface EbaRecord {
  bank_name: string;
  lei_code: string;
  period: string;
  ratios: EbaRatios;
  eu_average: EbaRatios;
  gaps_vs_eu_average: EbaRatios;
  composite_score: number;
}

export interface EbaScoresResponse {
  methodology: EbaMethodology;
  records: EbaRecord[];
}

// ─────────────────────────────────────────
// Types — Classification (griefs ACPR)
// ─────────────────────────────────────────

export interface ClassificationPrediction {
  category: string;
  score: number;
  threshold: number;
  predicted: boolean;
}

export interface ClassificationResponse {
  predictions: ClassificationPrediction[];
}

export interface ClassificationExample {
  decision_number: string;
  text: string;
  true_labels: string[];
}

export interface ClassificationExamplesResponse {
  examples: ClassificationExample[];
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

export async function fetchBdfStats(): Promise<BdfStats> {
  return apiFetch<BdfStats>('/banque-de-france/stats');
}

export async function fetchBdfNews(params?: { limit?: number; offset?: number }): Promise<NewsResponse> {
  const q = new URLSearchParams();
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.offset) q.set('offset', String(params.offset));
  return apiFetch<NewsResponse>(`/banque-de-france/news?${q}`);
}

export async function fetchBdfRag(
  question: string,
  nResults?: number
): Promise<RagResponse> {
  return apiFetch<RagResponse>('/banque-de-france/rag', {
    method: 'POST',
    body: JSON.stringify({ question, n_results: nResults ?? 5 }),
  });
}

export async function fetchBdfTopicModeling(): Promise<TopicModelingResponse> {
  return apiFetch<TopicModelingResponse>('/banque-de-france/ml/topic-modeling');
}

export async function fetchBdfEbaScores(): Promise<EbaScoresResponse> {
  return apiFetch<EbaScoresResponse>('/banque-de-france/ml/eba-scores');
}

export async function fetchBdfClassification(text: string): Promise<ClassificationResponse> {
  return apiFetch<ClassificationResponse>('/banque-de-france/ml/classification', {
    method: 'POST',
    body: JSON.stringify({ text }),
  });
}

export async function fetchBdfClassificationExamples(): Promise<ClassificationExamplesResponse> {
  return apiFetch<ClassificationExamplesResponse>('/banque-de-france/ml/classification/examples');
}
