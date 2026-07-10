variable "project_id" {
  description = "ID du projet GCP (gen-lang-client-0989575872)"
  type        = string
}

variable "sa_account_id" {
  description = "account_id du service account dbt (max 30 caractères, minuscules/chiffres/tirets)"
  type        = string
  default     = "pipeline-dbt"
}

variable "impersonator_member" {
  description = "Identité autorisée à impersonate le SA en local, format 'user:email@example.com'"
  type        = string
}

variable "region" {
  description = "Région GCP par défaut du provider"
  type        = string
  default     = "europe-west9"
}
