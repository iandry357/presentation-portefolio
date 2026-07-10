# ============================================================
# gcp/dbt_transformation/infra/main.tf
# Service Account dédié à l'exécution des transformations dbt
# Authentification : ADC + impersonation (pas de clé JSON)
# ============================================================

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "portfolio-emploi-tfstate"
    prefix = "gcp/dbt_transformation/infra"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_service_account" "pipeline_dbt" {
  project      = var.project_id
  account_id   = var.sa_account_id
  display_name = "Pipeline dbt - Observatoire Emploi"
  description  = "SA dédié aux transformations dbt sur emploi_marche.offres_brutes"
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "dbt_bigquery_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.pipeline_dbt.email}"
}

resource "google_project_iam_member" "dbt_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.pipeline_dbt.email}"
}

# Autorise l'identité locale (toi) à impersonate ce SA depuis ton poste,
# nécessaire pour l'authentification ADC en développement
# (target "dev" de profiles.yml).
resource "google_service_account_iam_member" "dbt_impersonation" {
  service_account_id = google_service_account.pipeline_dbt.name
  role                = "roles/iam.serviceAccountTokenCreator"
  member              = var.impersonator_member
}
