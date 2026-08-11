
import { 
  ChatResponse, CompanyProfile, CompanyProfileSummary, 
  ExperienceListItem, 
  Experience, 
  ExperienceFormData,
  Skill,
  ExternalJobOfferCreate,
  FeedbackCreate, FeedbackCreateResponse  } from '@/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
export const FT_BASE_URL = process.env.NEXT_PUBLIC_FT_BASE_URL;

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
  ExploreResponse,
  FilterOptions,
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
  if (filters.email_sources?.length) {
    filters.email_sources.forEach(s => params.append('email_sources', s));
  }

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

export async function createExternalJob(
  data: ExternalJobOfferCreate
): Promise<JobOfferDetail> {
  const response = await fetch(`${API_URL}/jobs/external`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });

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
  status: 'consulte' | 'postule' | 'enregistre'
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

export async function addManualJob(ft_id: string): Promise<JobOfferDetail> {
  const response = await fetch(`${API_URL}/jobs/manual`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ft_id }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// ============================================================================
// Sauvegarde des notes personnelles
// ============================================================================

export async function saveJobNotes(id: number, notes: string): Promise<void> {
  const response = await fetch(`${API_URL}/jobs/${id}/notes`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ notes }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
}

// ============================================================================
// Company Profiles — API calls
// ============================================================================

export async function getCompanies(): Promise<CompanyProfileSummary[]> {
  const response = await fetch(`${API_URL}/companies`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

export async function getCompany(id: number): Promise<CompanyProfile> {
  const response = await fetch(`${API_URL}/companies/${id}`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

export async function getCompanyByJob(jobId: number): Promise<CompanyProfile | null> {
  const response = await fetch(`${API_URL}/companies/by-job/${jobId}`);
  if (response.status === 404) return null;
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

// export async function generateCompany(
//   jobId: number,
//   companyName?: string
// ): Promise<CompanyProfile> {
export async function generateCompany(
  jobId: number,
  companyName?: string
): Promise<{ company_profile_id: number; message: string }> {
  const response = await fetch(`${API_URL}/companies/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    // body: JSON.stringify({ job_id: jobId, company_name: companyName ?? null }),
    body: JSON.stringify({ job_offer_id: jobId, name_input: companyName ?? '' }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

export async function refreshCompany(id: number): Promise<void> {
  const response = await fetch(`${API_URL}/companies/${id}/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
}

export async function recalculCompany(
  id: number,
  instruction?: string
): Promise<void> {
  const response = await fetch(`${API_URL}/companies/${id}/recalcul`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ instruction: instruction ?? null }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
}

export async function relaunchCompany(id: number): Promise<void> {
  const response = await fetch(`${API_URL}/companies/${id}/relaunch`, {
    method: 'POST',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
}

export async function deleteCompany(id: number): Promise<void> {
  const response = await fetch(`${API_URL}/companies/${id}`, {
    method: 'DELETE',
  });
  if (!response.ok && response.status !== 204) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
}

// ============================================================================
// CV CRUD - Experiences
// ============================================================================

export async function getExperiences(): Promise<ExperienceListItem[]> {
  const response = await fetch(`${API_URL}/api/cv/experiences`);
  if (!response.ok) {
    throw new Error('Erreur lors de la récupération des expériences');
  }
  return response.json();
}

export async function getExperience(id: number): Promise<Experience> {
  const response = await fetch(`${API_URL}/api/cv/experiences/${id}`);
  if (!response.ok) {
    throw new Error('Erreur lors de la récupération de l\'expérience');
  }
  return response.json();
}

export async function createExperience(
  data: ExperienceFormData,
  code: string
): Promise<Experience> {
  const response = await fetch(`${API_URL}/api/cv/experiences`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CV-Edit-Code': code,
    },
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    if (response.status === 403) {
      throw new Error('Code de sécurité invalide');
    }
    throw new Error('Erreur lors de la création de l\'expérience');
  }
  
  return response.json();
}

export async function updateExperience(
  id: number,
  data: Partial<ExperienceFormData>,
  code: string
): Promise<Experience> {
  const response = await fetch(`${API_URL}/api/cv/experiences/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-CV-Edit-Code': code,
    },
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    if (response.status === 403) {
      throw new Error('Code de sécurité invalide');
    }
    throw new Error('Erreur lors de la modification de l\'expérience');
  }
  
  return response.json();
}

export async function deleteExperience(
  id: number,
  code: string
): Promise<void> {
  const response = await fetch(`${API_URL}/api/cv/experiences/${id}`, {
    method: 'DELETE',
    headers: {
      'X-CV-Edit-Code': code,
    },
  });
  
  if (!response.ok) {
    if (response.status === 403) {
      throw new Error('Code de sécurité invalide');
    }
    throw new Error('Erreur lors de la suppression de l\'expérience');
  }
}

export async function retryExperienceEmbeddings(
  id: number,
  code: string
): Promise<void> {
  const response = await fetch(
    `${API_URL}/api/cv/experiences/${id}/retry-embeddings`,
    {
      method: 'POST',
      headers: {
        'X-CV-Edit-Code': code,
      },
    }
  );
  
  if (!response.ok) {
    if (response.status === 403) {
      throw new Error('Code de sécurité invalide');
    }
    throw new Error('Erreur lors du redémarrage de la génération des embeddings');
  }
}

// ============================================================================
// CV CRUD - Skills (liste pour sélection)
// ============================================================================

export async function getSkills(): Promise<Skill[]> {
  const response = await fetch(`${API_URL}/api/cv/skills`);
  if (!response.ok) {
    throw new Error('Erreur lors de la récupération des compétences');
  }
  return response.json();
}

/**
 * Soumettre un feedback
 */
export async function submitFeedback(
  feedback: FeedbackCreate
): Promise<FeedbackCreateResponse> {
  const response = await fetch(`${API_URL}/feedback`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(feedback),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Erreur lors de l'envoi du feedback");
  }

  return response.json();
}

/**
 * Initialiser la session en base de données
 */
export async function initializeSession(sessionId: string): Promise<void> {
  console.log('📡 Calling /session/init with:', sessionId);
  try {
    const response = await fetch(`${API_URL}/session/init`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ session_id: sessionId }),
    });

    console.log('📡 Response status:', response.status);
    
    if (!response.ok) {
      const error = await response.json();
      console.error("❌ Failed to initialize session:", error);
    } else {
      const data = await response.json();
      console.log("✅ Session init response:", data);
    }
  } catch (error) {
    console.error("❌ Error initializing session:", error);
  }
}

export async function updateJob(
  jobId: number,
  data: Partial<ExternalJobOfferCreate>
): Promise<JobOfferDetail> {
  const res = await fetch(`${API_URL}/jobs/${jobId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Erreur lors de la mise à jour');
  return res.json();
}

export async function fetchGmailAlerts(): Promise<{ inserted: number; skipped: number; errors: number }> {
  const res = await fetch(`${API_URL}/jobs/gmail/fetch`, { method: 'POST' });
  if (!res.ok) throw new Error('Erreur lors de la récupération Gmail');
  return res.json();
}

// ============================================================================
// Explore — Marché BigQuery
// ============================================================================

export async function getExploreOffers(params: {
  page?: number;
  page_size?: number;
  source?: string;
  type_contrat?: string;
  localisation_libelle?: string;
  periode_jours?: number;
  titre?: string;
  entreprise_nom?: string;
  recherche_mot_cle?: string;
}): Promise<ExploreResponse> {
  const p = new URLSearchParams();
  if (params.page)               p.set('page', String(params.page));
  if (params.page_size)          p.set('page_size', String(params.page_size));
  if (params.source)             p.set('source', params.source);
  if (params.type_contrat)       p.set('type_contrat', params.type_contrat);
  if (params.localisation_libelle) p.set('localisation_libelle', params.localisation_libelle);
  if (params.periode_jours)      p.set('periode_jours', String(params.periode_jours));
  if (params.titre)              p.set('titre', params.titre);
  if (params.entreprise_nom)              p.set('entreprise_nom', params.entreprise_nom);
  if (params.recherche_mot_cle)           p.set('recherche_mot_cle', params.recherche_mot_cle);

  const response = await fetch(`${API_URL}/explore?${p.toString()}`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

export async function getExploreFilters(): Promise<FilterOptions> {
  const response = await fetch(`${API_URL}/explore/filters`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}