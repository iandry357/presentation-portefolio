# Infra
variable "region" {
  description = "Region Scaleway"
  type        = string
  default     = "fr-par"
}

variable "zone" {
  description = "Zone Scaleway"
  type        = string
  default     = "fr-par-1"
}

variable "project_id" {
  description = "Scaleway Project ID"
  type        = string
  sensitive   = true
}

# Registry
variable "registry_name" {
  description = "Nom du Container Registry"
  type        = string
  default     = "portfolio-sv-registry"
}

# Container Namespace
variable "namespace_name" {
  description = "Nom du namespace Serverless Containers"
  type        = string
  default     = "portfolio-cv"
}

# Backend container
variable "backend_image" {
  description = "Image Docker backend"
  type        = string
  default     = "rg.fr-par.scw.cloud/portfolio-sv-registry/backend:latest"
}

variable "cors_origins" {
  description = "CORS origins autorisees"
  type        = string
}

# Database
variable "db_name" {
  description = "Nom de l'instance PostgreSQL"
  type        = string
  default     = "portefolio-cv-db"
}

variable "postgres_host" {
  description = "IP hôte PostgreSQL"
  type        = string
  sensitive   = true
}

variable "db_user" {
  description = "Utilisateur PostgreSQL"
  type        = string
  default     = "portefolio-credential"
}

# Secrets
variable "gemini_api_key" {
  description = "Gemini API Key"
  type        = string
  sensitive   = true
}

variable "secret_key" {
  description = "Secret Key application"
  type        = string
  sensitive   = true
}

variable "mistral_api_key" {
  description = "Mistral API Key"
  type        = string
  sensitive   = true
}

variable "groq_api_key" {
  description = "Groq API Key"
  type        = string
  sensitive   = true
}

variable "langsmith_api_key" {
  description = "LangSmith API Key"
  type        = string
  sensitive   = true
}

variable "langsmith_project" {
  description = "LangSmith project name"
  type        = string
  default     = "portfolio-rag"
}

variable "langchain_tracing_v2" {
  description = "Enable LangChain tracing"
  type        = string
  default     = "true"
}

variable "langfuse_public_key" {
  description = "Langfuse public key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "langfuse_secret_key" {
  description = "Langfuse secret key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "langfuse_host" {
  description = "Langfuse host URL"
  type        = string
  default     = "https://cloud.langfuse.com"
}

variable "voyage_api_key" {
  description = "VoyageAI API Key"
  type        = string
  sensitive   = true
}

variable "france_travail_client_id" {
  description = "France Travail Client ID"
  type        = string
  sensitive   = true
}

variable "france_travail_client_secret" {
  description = "France Travail Client Secret"
  type        = string
  sensitive   = true
}

variable "database_url" {
  description = "URL complète PostgreSQL"
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API Key"
  type        = string
  sensitive   = true
}

variable "postgres_password" {
  description = "Mot de passe PostgreSQL"
  type        = string
  sensitive   = true
}

variable "serper_api_key" {
  description = "Clé API Serper pour la recherche web"
  type        = string
  sensitive   = true
}

variable "cv_edit_secret_code" {
  description = "Code de sécurité pour édition du CV"
  type        = string
  sensitive   = true
}

variable "scw_access_key" {
  description = "Scaleway Access Key"
  type        = string
  sensitive   = true
}

variable "scw_secret_key" {
  description = "Scaleway Secret Key"
  type        = string
  sensitive   = true
}

variable "gcp_service_account_json" {
  description = "GCP Service Account JSON pour BigQuery"
  type        = string
  sensitive   = true
}

variable "chroma_password" {
  description = "ChromaDB auth password"
  type        = string
  sensitive   = true
}

variable "frontend_image" {
  description = "Image Docker frontend"
  type        = string
  default     = "rg.fr-par.scw.cloud/portfolio-sv-registry/frontend:latest"
}

variable "gcp_service_account_json_sanofi" {
  description = "GCP Service Account JSON Sanofi"
  type        = string
  sensitive   = true
}

variable "gcp_service_account_json_savencia" {
  description = "GCP Service Account JSON Savencia"
  type        = string
  sensitive   = true
}