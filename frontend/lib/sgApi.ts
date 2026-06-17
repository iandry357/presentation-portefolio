const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ─────────────────────────────────────────
// Types
// ─────────────────────────────────────────

export interface SgStats {
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
}

export interface RagResponse {
  answer: string;
  sources: RagSource[];
  model_used: string;
  tokens_used: number;
}

export interface NerEntity {
  text: string;
  label: string;
  score: number;
  start: number;
  end: number;
}

export interface NerResponse {
  entities: NerEntity[];
}

export interface YoloDetection {
  class_name: string;
  score: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface YoloResponse {
  detections: YoloDetection[];
}

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

export interface QwenResponse {
  generated_text: string;
  model_type: string;
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

export async function fetchSgStats(): Promise<SgStats> {
  return apiFetch<SgStats>('/sg/stats');
}

export async function fetchSgNews(params?: { limit?: number; offset?: number }): Promise<NewsResponse> {
  const q = new URLSearchParams();
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.offset) q.set('offset', String(params.offset));
  return apiFetch<NewsResponse>(`/sg/news?${q}`);
}

export async function fetchSgRag(
  question: string,
  nResults?: number
): Promise<RagResponse> {
  return apiFetch<RagResponse>('/sg/rag', {
    method: 'POST',
    body: JSON.stringify({ question, n_results: nResults ?? 5 }),
  });
}

export async function fetchSgTopicModeling(): Promise<TopicModelingResponse> {
  return apiFetch<TopicModelingResponse>('/sg/ml/topic-modeling');
}

export async function fetchSgNer(text: string): Promise<NerResponse> {
  return apiFetch<NerResponse>('/sg/ml/ner', {
    method: 'POST',
    body: JSON.stringify({ text }),
  });
}

export async function fetchSgYolo(file: File): Promise<YoloResponse> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE}/sg/ml/yolo`, { method: 'POST', body: form });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API error ${res.status}: ${err}`);
  }
  return res.json();
}

export async function fetchSgQwen(
  prompt: string,
  maxNewTokens?: number
): Promise<QwenResponse> {
  return apiFetch<QwenResponse>('/sg/ml/qwen', {
    method: 'POST',
    body: JSON.stringify({ prompt, max_new_tokens: maxNewTokens ?? 200 }),
  });
}