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

variable "tfstate_bucket_name" {
  description = "Nom du bucket Object Storage pour le state Terraform"
  type        = string
  default     = "portfolio-tfstate"
}