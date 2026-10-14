variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "europe-west9"
}

variable "bq_location" {
  description = "BigQuery dataset location"
  type        = string
  default     = "EU"
}

variable "dataset_source_id" {
  description = "Dataset source en lecture seule (géré dans gcp/infra)"
  type        = string
  default     = "emploi_marche"
}

variable "config_bucket_name" {
  description = "Bucket de configuration en lecture seule (liste des entreprises exclues, géré dans gcp/infra)"
  type        = string
  default     = "portfolio-emploi-config"
}
