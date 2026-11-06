const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ─────────────────────────────────────────
// Types
// ─────────────────────────────────────────

export interface SqliStats {
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

export interface RagSource {
  id: string;
  source: string;
  title: string;
  url: string | null;
  score: number | null;
  date?: string | null;
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
  summary?: string;
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

export async function fetchSqliStats(): Promise<SqliStats> {
  return apiFetch<SqliStats>('/sqli/stats');
}

export async function fetchSqliNews(params?: { limit?: number; offset?: number }): Promise<NewsResponse> {
  const q = new URLSearchParams();
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.offset) q.set('offset', String(params.offset));
  return apiFetch<NewsResponse>(`/sqli/news?${q}`);
}

export async function fetchSqliRag(
  question: string,
  nResults?: number
): Promise<RagResponse> {
  return apiFetch<RagResponse>('/sqli/rag', {
    method: 'POST',
    body: JSON.stringify({ question, n_results: nResults ?? 5 }),
  });
}

export async function fetchSqliTopicModeling(): Promise<TopicModelingResponse> {
  return apiFetch<TopicModelingResponse>('/sqli/ml/topic-modeling');
}
