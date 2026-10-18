
import { 
  ChatResponse, CompanyProfile, CompanyProfileSummary, 
  ExperienceListItem, 
  Experience, 
  ExperienceFormData,
  Skill,
  ExternalJobOfferCreate,
  FeedbackCreate, FeedbackCreateResponse  } from '@/types';

const API_URL = '/backend';
export const FT_BASE_URL = process.env.NEXT_PUBLIC_FT_BASE_URL;

// Erreur HTTP de l'API : `message` = `detail` du backend (ou « HTTP <statut> »)
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;   // sérialisé en JSON
}

// Abonné unique, notifié sur tout 403 (accès perdu ou quota) : AccessProvider se resynchronise.
let onForbidden: (() => void) | null = null;
export function setForbiddenHandler(handler: (() => void) | null) {
  onForbidden = handler;
}

// Appel JSON vers le backend (via le proxy). Corps vide ou 204 : renvoie undefined.
async function request<T>(path: string, { method = 'GET', body }: RequestOptions = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method,
    ...(body !== undefined && {
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  });

  if (!response.ok) {
    if (response.status === 403) onForbidden?.();
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(response.status, error.detail || `HTTP ${response.status}`);
  }

  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

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

  return request<JobListResponse>(`/jobs?${params.toString()}`);
}

// ============================================================================
// Détail d'une offre
// ============================================================================

export async function getJob(id: number): Promise<JobOfferDetail> {
  return request<JobOfferDetail>(`/jobs/${id}`);
}

export async function createExternalJob(
  data: ExternalJobOfferCreate
): Promise<JobOfferDetail> {
  return request<JobOfferDetail>('/jobs/external', { method: 'POST', body: data });
}

// ============================================================================
// Fiche enrichie
// ============================================================================

export async function getJobEnriched(id: number): Promise<JobEnriched> {
  return request<JobEnriched>(`/jobs/${id}/enriched`);
}

// ============================================================================
// Mise à jour statut
// ============================================================================

export async function updateJobStatus(
  id: number,
  status: 'consulte' | 'postule' | 'enregistre'
): Promise<void> {
  return request<void>(`/jobs/${id}/status`, { method: 'PATCH', body: { status } });
}

// ============================================================================
// Enrichissement initial
// ============================================================================

export async function enrichJob(id: number): Promise<JobEnriched> {
  return request<JobEnriched>(`/jobs/${id}/enrich`, { method: 'POST' });
}

// ============================================================================
// Recalcul avec instruction
// ============================================================================

export async function recalculJob(
  id: number,
  instruction: string
): Promise<JobEnriched> {
  return request<JobEnriched>(`/jobs/${id}/recalcul`, { method: 'POST', body: { instruction } });
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
  return request('/jobs/pipeline/trigger', { method: 'POST', body: { region: region ?? null } });
}

export async function resetJobs() {
  return request<{ message: string; deleted: number }>('/jobs/reset', { method: 'DELETE' });
}

export async function addManualJob(ft_id: string): Promise<JobOfferDetail> {
  return request<JobOfferDetail>('/jobs/manual', { method: 'POST', body: { ft_id } });
}

// ============================================================================
// Sauvegarde des notes personnelles
// ============================================================================

export async function saveJobNotes(id: number, notes: string): Promise<void> {
  return request<void>(`/jobs/${id}/notes`, { method: 'PATCH', body: { notes } });
}

// ============================================================================
// Company Profiles — API calls
// ============================================================================

export async function getCompanies(): Promise<CompanyProfileSummary[]> {
  return request<CompanyProfileSummary[]>('/companies');
}

export async function getCompany(id: number): Promise<CompanyProfile> {
  return request<CompanyProfile>(`/companies/${id}`);
}

export async function getCompanyByJob(jobId: number): Promise<CompanyProfile | null> {
  try {
    return await request<CompanyProfile>(`/companies/by-job/${jobId}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

// export async function generateCompany(
//   jobId: number,
//   companyName?: string
// ): Promise<CompanyProfile> {
export async function generateCompany(
  jobId: number,
  companyName?: string
): Promise<{ company_profile_id: number; message: string }> {
  return request('/companies/generate', {
    method: 'POST',
    // body: { job_id: jobId, company_name: companyName ?? null },
    body: { job_offer_id: jobId, name_input: companyName ?? '' },
  });
}

export async function refreshCompany(id: number): Promise<void> {
  return request<void>(`/companies/${id}/refresh`, { method: 'POST', body: {} });
}

export async function recalculCompany(
  id: number,
  instruction?: string
): Promise<void> {
  return request<void>(`/companies/${id}/recalcul`, {
    method: 'POST',
    body: { instruction: instruction ?? null },
  });
}

export async function relaunchCompany(id: number): Promise<void> {
  return request<void>(`/companies/${id}/relaunch`, { method: 'POST' });
}

export async function deleteCompany(id: number): Promise<void> {
  return request<void>(`/companies/${id}`, { method: 'DELETE' });   // 204 géré par le helper
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
  return request<JobOfferDetail>(`/jobs/${jobId}`, { method: 'PATCH', body: data });
}

export async function fetchGmailAlerts(): Promise<{ inserted: number; skipped: number; errors: number }> {
  return request<{ inserted: number; skipped: number; errors: number }>('/jobs/gmail/fetch', { method: 'POST' });
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

  return request<ExploreResponse>(`/explore?${p.toString()}`);
}

export async function getExploreFilters(): Promise<FilterOptions> {
  return request<FilterOptions>('/explore/filters');
}

// ============================================================================
// Accès privé — statut, déverrouillage, verrouillage
// ============================================================================

import { AccessStatus, UnlockResult } from '@/types';

// Lecture seule côté serveur : ne prolonge pas la session
export async function getAccessStatus(): Promise<AccessStatus> {
  const response = await fetch(`${API_URL}/access/status`, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

export async function unlockAccess(code: string): Promise<UnlockResult> {
  const response = await fetch(`${API_URL}/access/unlock`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  });

  if (response.ok) {
    return { ok: true, status: await response.json() };
  }

  const error = await response.json().catch(() => ({}));
  const message =
    typeof error.detail === 'string' ? error.detail : `HTTP ${response.status}`;

  if (response.status === 429) {
    const retryAfter = Number(response.headers.get('Retry-After'));
    return {
      ok: false,
      reason: 'blocked',
      message,
      retryAfterSeconds: retryAfter > 0 ? retryAfter : undefined,
    };
  }
  return { ok: false, reason: response.status === 401 ? 'invalid' : 'error', message };
}

export async function lockAccess(): Promise<void> {
  const response = await fetch(`${API_URL}/access/lock`, { method: 'POST' });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
}


// ============================================================================
// Top Offres — API calls
// ============================================================================

import {
  TopResponse,
  TopStatsResponse,
  TopDecisionType,
  TopDecisionResponse,
  TopTypeEntreprise,
  TypeEntrepriseCorrigeable,
} from '@/types';

// Public
export async function getTopStats(jours: number): Promise<TopStatsResponse> {
  return request<TopStatsResponse>(`/top-offres/stats?jours=${jours}`);
}

// Privé : les deux listes (onglets) d'un coup, avec les compteurs
export async function getTop(params: {
  jours: number;
  inclureExclues: boolean;
}): Promise<TopResponse> {
  const p = new URLSearchParams({
    jours: String(params.jours),
    inclure_exclues: String(params.inclureExclues),
  });
  return request<TopResponse>(`/top-offres/top?${p.toString()}`);
}

// « Intéressé » : un doublon détecté (resultat = 'doublon_detecte') ne crée rien ;
// rappeler avec `confirmer` (créer quand même) ou `utiliser_job_offer_id` (rattacher à une offre existante).
export async function createTopDecision(body: {
  id_unique: string;
  decision: TopDecisionType;
  confirmer?: boolean;
  utiliser_job_offer_id?: number;
}): Promise<TopDecisionResponse> {
  return request<TopDecisionResponse>('/top-offres/decisions', { method: 'POST', body });
}

// L'id_unique d'une alerte e-mail est un lien de suivi (« ? », « & », « / ») : paramètre de requête encodé
export async function deleteTopDecision(idUnique: string): Promise<{ ok: boolean }> {
  const p = new URLSearchParams({ id_unique: idUnique });
  return request<{ ok: boolean }>(`/top-offres/decisions?${p.toString()}`, { method: 'DELETE' });
}

export async function setTypeEntreprise(
  nomNormalise: string,
  body: { type_entreprise: TypeEntrepriseCorrigeable; commentaire?: string | null }
): Promise<TopTypeEntreprise> {
  return request<TopTypeEntreprise>(
    `/top-offres/types-entreprise/${encodeURIComponent(nomNormalise)}`,
    { method: 'PUT', body }
  );
}

// Supprime la correction : le type affiché redevient l'automatique
export async function deleteTypeEntreprise(nomNormalise: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(
    `/top-offres/types-entreprise/${encodeURIComponent(nomNormalise)}`,
    { method: 'DELETE' }
  );
}

// ============================================================================
// Top Offres — Entreprises
// ============================================================================

import { EntreprisesResponse, OffresEntrepriseResponse, OrdreTri, TriEntreprises } from '@/types';

export async function getEntreprises(params: {
  jours: number;
  tri: TriEntreprises;
  ordre: OrdreTri;
  typeEntreprise?: string;
  secteur?: string;
  q?: string;
  inclureExclues: boolean;
  limite: number;
}): Promise<EntreprisesResponse> {
  const p = new URLSearchParams({
    jours: String(params.jours),
    tri: params.tri,
    ordre: params.ordre,
    inclure_exclues: String(params.inclureExclues),
    limite: String(params.limite),
  });
  if (params.typeEntreprise) p.set('type_entreprise', params.typeEntreprise);
  if (params.secteur) p.set('secteur', params.secteur);
  if (params.q) p.set('q', params.q);
  return request<EntreprisesResponse>(`/top-offres/entreprises?${p.toString()}`);
}

// Offres d'une entreprise, à la demande : la clé (nom normalisé) passe en paramètre de requête
export async function getOffresEntreprise(
  entreprise: string,
  jours: number
): Promise<OffresEntrepriseResponse> {
  const p = new URLSearchParams({ entreprise, jours: String(jours) });
  return request<OffresEntrepriseResponse>(`/top-offres/entreprises/offres?${p.toString()}`);
}

