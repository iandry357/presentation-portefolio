
import { ChatResponse } from '@/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function sendMessage(
  message: string,
  sessionId: string
): Promise<ChatResponse> {
  const response = await fetch(`${API_URL}/api/chat/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      session_id: sessionId,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

export function getPdfUrl(): string {
  return `${API_URL}/api/cv/view`;
}

// ============================================================================
// Jobs — API calls
// Coller à la fin de lib/api.ts
// ============================================================================

import {
  JobListResponse,
  JobOfferDetail,
  JobEnriched,
  JobFilters,
} from '@/types';

// ============================================================================
// Liste des offres avec filtres
// ============================================================================

export async function getJobs(filters: JobFilters): Promise<JobListResponse> {
  const params = new URLSearchParams();

  params.set('page', String(filters.page));
  params.set('page_size', String(filters.page_size));
  params.set('hide_consulted', String(filters.hide_consulted));

  if (filters.contract_type) params.set('contract_type', filters.contract_type);
  if (filters.status)        params.set('status', filters.status);
  if (filters.postal_code)   params.set('postal_code', filters.postal_code);
  if (filters.max_days_old)  params.set('max_days_old', String(filters.max_days_old));

  const response = await fetch(`${API_URL}/jobs?${params.toString()}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// ============================================================================
// Détail d'une offre
// ============================================================================

export async function getJob(id: number): Promise<JobOfferDetail> {
  const response = await fetch(`${API_URL}/jobs/${id}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// ============================================================================
// Fiche enrichie
// ============================================================================

export async function getJobEnriched(id: number): Promise<JobEnriched> {
  const response = await fetch(`${API_URL}/jobs/${id}/enriched`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// ============================================================================
// Mise à jour statut
// ============================================================================

export async function updateJobStatus(
  id: number,
  status: 'consulte' | 'postule'
): Promise<void> {
  const response = await fetch(`${API_URL}/jobs/${id}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
}

// ============================================================================
// Enrichissement initial
// ============================================================================

export async function enrichJob(id: number): Promise<JobEnriched> {
  const response = await fetch(`${API_URL}/jobs/${id}/enrich`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// ============================================================================
// Recalcul avec instruction
// ============================================================================

export async function recalculJob(
  id: number,
  instruction: string
): Promise<JobEnriched> {
  const response = await fetch(`${API_URL}/jobs/${id}/recalcul`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ instruction }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// ============================================================================
// Déclenchement manuel du pipeline (dev uniquement)
// ============================================================================

export async function triggerPipeline(region?: string): Promise<{
  message: string;
  offers_collected: number;
  offers_scored: number;
  offers_enriched: number;
}> {
  const response = await fetch(`${API_URL}/jobs/pipeline/trigger`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ region: region ?? null }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

export async function resetJobs() {
  const response = await fetch(`${API_URL}/jobs/reset`, {  // ← adapte le chemin si tu utilises un proxy ou une base url différente
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
    },
    // credentials: 'include',   // si tu as de l'auth plus tard
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Erreur ${response.status}`);
  }

  return response.json();
}