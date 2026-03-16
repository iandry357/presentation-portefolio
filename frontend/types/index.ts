export interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  timestamp: number;
}

export interface Source {
  type: 'experience' | 'project' | 'formation';
  id: number;
  title: string;
  score: number;
}

export interface ChatResponse {
  query_id: string;
  response: string;
  sources: Source[];
  tokens_used: number;
  cost: number;
  provider_used: string;
  questions_count: number;
  questions_remaining: number;
}

export interface Session {
  sessionId: string;
  createdAt: number;
  questionsCount: number;
  lastQuestionAt: number;
}

// ============================================================================
// Jobs — Types France Travail
// ============================================================================

export type JobStatus = 'nouveau' | 'existant' | 'ferme' | 'consulte' | 'postule' | 'enregistre' | 'manuel';

export interface JobOfferSummary {
  id: number;
  ft_id: string;
  title: string;
  description: string | null;
  company_name: string | null;
  location_label: string | null;
  contract_type: string | null;
  contract_label: string | null;
  work_time: string | null;
  salary_label: string | null;
  experience_label: string | null;
  sector_label: string | null;
  offer_url: string | null;
  ft_published_at: string | null;
  status: JobStatus;
  applied_at: string | null;
  has_enriched: boolean;
  notes: string | null;
}

export interface JobOfferDetail extends JobOfferSummary {
  // description: string | null;
  rome_code: string | null;
  location_postal_code: string | null;
  location_lat: number | null;
  location_lng: number | null;
  company_description: string | null;
  company_url: string | null;
  company_profile_id: number | null;
  naf_code: string | null;
  raw_data: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface JobEnriched {
  id: number;
  job_offer_id: number;
  parsed_data: Record<string, unknown> | null;
  analysis: Record<string, unknown> | null;
  summary: string | null;
  recalcul_count: number;
  recalcul_remaining: number;
  recalcul_history: Array<{ instruction: string; recalcul_at: string }> | null;
  created_at: string;
  updated_at: string;
}

export interface JobListResponse {
  total: number;
  items: JobOfferSummary[];
}

export interface JobFilters {
  contract_type?: string;
  status?: string;
  hide_consulted: boolean;
  postal_code?: string;
  max_days_old?: number;
  page: number;
  page_size: number;
}

// ============================================================================
// Company Profiles
// ============================================================================

export type CompanyLayerStatus = 'pending' | 'done' | 'failed';

export interface CompanyProfileSummary {
  id: number;
  name: string;
  memo: string | null;
  discovery_status: CompanyLayerStatus;
  legal_status: CompanyLayerStatus;
  actualites_status: CompanyLayerStatus;
  memo_status: CompanyLayerStatus;
  recalcul_count: number;
  actualites_updated_at: string | null;
  created_at: string;
}

export interface CompanyProfile extends CompanyProfileSummary {
  name_input: string;
  discovery: Record<string, unknown> | null;
  legal_data: Record<string, unknown> | null;
  actualites: Record<string, unknown> | null;
  recalcul_history: Array<{ instruction: string; recalcul_at: string }> | null;
  updated_at: string;
}

// ============================================================================
// CV CRUD - Skills
// ============================================================================

export interface Skill {
  id: number;
  name: string;
  category: string | null;
  proficiency_level: string | null;
}

// ============================================================================
// CV CRUD - Projects
// ============================================================================

export interface Project {
  id: number;
  experience_id: number;
  name: string;
  project_type: string;
  description: string;
  objective: string;
  problem: string;
  solution: string;
  results: string;
  impact: string;
  stack: string;
  collaborators: string | null;
  start_date: string | null;
  end_date: string | null;
  duration_months: number | null;
  embedding_status: 'done' | 'pending' | 'failed';
  created_at: string;
  updated_at: string;
}

export interface ProjectFormData {
  id?: number;
  name: string;
  project_type: string;
  description: string;
  objective: string;
  problem: string;
  solution: string;
  results: string;
  impact: string;
  stack: string;
  collaborators?: string;
  start_date?: string;
  end_date?: string;
  duration_months?: number;
}

// ============================================================================
// CV CRUD - Experiences
// ============================================================================

export interface Experience {
  id: number;
  company: string;
  role: string;
  mission_type: string;
  location: string;
  start_date: string;
  end_date: string | null;
  duration_months: number | null;
  context: string;
  is_stage: boolean;
  embedding_status: 'done' | 'pending' | 'failed';
  projects: Project[];
  skills: Skill[];
  created_at: string;
  updated_at: string;
}

export interface ExperienceListItem {
  id: number;
  company: string;
  role: string;
  start_date: string;
  end_date: string | null;
  location: string;
  is_stage: boolean;
  embedding_status: 'done' | 'pending' | 'failed';
  project_count: number;
}

export interface ExperienceFormData {
  company: string;
  role: string;
  mission_type: string;
  location: string;
  start_date: string;
  end_date?: string;
  duration_months?: number;
  context: string;
  is_stage: boolean;
  projects: ProjectFormData[];
  skill_ids: number[];
}

// ============================================================================
// Feedback Types
// ============================================================================

export interface FeedbackAnswer {
  question_key: string;
  comment?: string;
}

export interface FeedbackCreate {
  session_id: string;
  page_route: string;
  page_type: string;
  rating: number;
  job_offer_id?: number;
  company_profile_id?: number;
  answers: FeedbackAnswer[];
}

export interface FeedbackCreateResponse {
  id: number;
  message: string;
}