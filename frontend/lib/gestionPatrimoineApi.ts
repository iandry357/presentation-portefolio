const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ─────────────────────────────────────────
// Types
// ─────────────────────────────────────────

export interface Profil {
  thematique: string;
  age: number;
  situation_familiale: string;
  patrimoine_global: number;
  objectif: string;
  details: Record<string, unknown>;
}

export interface GenererProfilResponse {
  session_id: string;
  profil: Profil;
}

export interface ArticleCite {
  numero_article: string;
  url_source: string;
}

export interface ChatResponse {
  texte: string;
  articles_cites: ArticleCite[];
  latence_ms: number;
}

export const THEMATIQUES = [
  { value: 'donations_successions', label: 'Donations / Successions' },
  { value: 'ifi', label: 'IFI' },
  { value: 'plus_values', label: 'Plus-values' },
  { value: 'assurance_vie', label: 'Assurance-vie' },
  { value: 'per', label: 'PER / épargne retraite' },
] as const;

// ─────────────────────────────────────────
// Fetch helper
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

export async function genererProfil(thematique?: string): Promise<GenererProfilResponse> {
  return apiFetch<GenererProfilResponse>('/gestion-patrimoine/profil', {
    method: 'POST',
    body: JSON.stringify({ thematique: thematique ?? null }),
  });
}

export async function envoyerMessage(sessionId: string, message?: string): Promise<ChatResponse> {
  return apiFetch<ChatResponse>('/gestion-patrimoine/chat', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, message: message ?? null }),
  });
}
