variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "gen-lang-client-0989575872"
}

variable "region" {
  description = "GCP region principale"
  type        = string
  default     = "europe-west9"
}

variable "region_bq" {
  description = "Région BigQuery (multi-region EU pour conformité RGPD)"
  type        = string
  default     = "eu"
}

variable "sa_email" {
  description = "Email du Service Account pipeline-emploi"
  type        = string
  default     = "pipeline-emploi@gen-lang-client-0989575872.iam.gserviceaccount.com"
}

# ── Valeurs des secrets (injectées via TF_VAR_* en CI ou en local) ────────────
# Ne jamais hardcoder ces valeurs dans les fichiers .tf

variable "ft_client_id" {
  description = "France Travail API client ID"
  type        = string
  sensitive   = true
}

variable "ft_client_secret" {
  description = "France Travail API client secret"
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  sensitive   = true
}

variable "gmail_credentials_json" {
  description = "Gmail OAuth2 credentials JSON"
  type        = string
  sensitive   = true
}

variable "gmail_token_json" {
  description = "Gmail OAuth2 token JSON"
  type        = string
  sensitive   = true
}

# ── Image Cloud Run ───────────────────────────────────────────────────────────

variable "sync_job_image" {
  description = "Image Docker du Cloud Run Job (Artifact Registry)"
  type        = string
  default = "europe-west9-docker.pkg.dev/gen-lang-client-0989575872/sync-job-registry/sync-ft-bigquery:latest"
}