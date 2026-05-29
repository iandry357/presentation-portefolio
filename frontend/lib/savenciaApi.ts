const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ─────────────────────────────────────────
// Types
// ─────────────────────────────────────────

export interface SavenciaStats {
  total_news: number;
  total_savencia_news: number;
  total_agroalimentaire_ia: number;
  last_updated: string | null;
}

export interface NewsItem {
  id: string;
  title: string;
  date: string | null;
  source_name: string | null;
  feed_name: string | null;
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

// ─────────────────────────────────────────
// Topic Modeling
// ─────────────────────────────────────────

export interface TopicItem {
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
  sources: {
    savencia_news: number;
    agroalimentaire_ia: number;
  };
  topics: TopicItem[];
  docs: TopicDoc[];
}

// ─────────────────────────────────────────
// ViT Inference
// ─────────────────────────────────────────

export interface VitInferenceResponse {
  cheese_type: string;
  ripeness: string;
  confidence: number;
  class_name: string;
  all_probabilities: Record<string, number>;
  heatmap_base64: string;
  model_version: string;
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

export async function fetchSavenciaStats(): Promise<SavenciaStats> {
  return apiFetch<SavenciaStats>('/savencia/stats');
}

export async function fetchNews(params?: {
  limit?: number;
  feed_name?: string;
}): Promise<NewsResponse> {
  const q = new URLSearchParams();
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.feed_name) q.set('feed_name', params.feed_name);
  return apiFetch<NewsResponse>(`/savencia/news?${q}`);
}

export async function fetchRag(
  question: string,
  nResults?: number
): Promise<RagResponse> {
  return apiFetch<RagResponse>('/savencia/rag', {
    method: 'POST',
    body: JSON.stringify({
      question,
      n_results: nResults ?? 5,
    }),
  });
}

export async function fetchTopicModeling(): Promise<TopicModelingResponse> {
  return apiFetch<TopicModelingResponse>('/savencia/ml/topic-modeling');
}

export async function fetchVitInference(file: File): Promise<VitInferenceResponse> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/savencia/ml/vit-inference`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API error ${res.status}: ${err}`);
  }
  return res.json();
}