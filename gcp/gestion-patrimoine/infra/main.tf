terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "portfolio-emploi-tfstate"
    prefix = "gcp/gestion-patrimoine/infra"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ─────────────────────────────────────────
# Service Account Pipeline
# ─────────────────────────────────────────

resource "google_service_account" "pipeline_gestion_patrimoine" {
  account_id   = "pipeline-gestion-patrimoine"
  display_name = "Pipeline Gestion Patrimoine — ETL + BigQuery"
  description  = "Service account dédié au pipeline ETL Gestion Patrimoine (collecte Légifrance, transformation, chargement BigQuery)"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "pipeline_gestion_patrimoine_bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.pipeline_gestion_patrimoine.email}"
}

resource "google_project_iam_member" "pipeline_gestion_patrimoine_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.pipeline_gestion_patrimoine.email}"
}

resource "google_service_account_key" "pipeline_gestion_patrimoine_key" {
  service_account_id = google_service_account.pipeline_gestion_patrimoine.name
}

# ─────────────────────────────────────────
# Service Account Terraform CI/CD
# ─────────────────────────────────────────

resource "google_service_account" "terraform_gestion_patrimoine" {
  account_id   = "terraform-gestion-patrimoine"
  display_name = "Terraform Gestion Patrimoine — CI/CD GitHub Actions"
  description  = "Service account dédié Terraform CI/CD pour l'infra Gestion Patrimoine"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "terraform_gestion_patrimoine_sa_admin" {
  project = var.project_id
  role    = "roles/iam.serviceAccountAdmin"
  member  = "serviceAccount:${google_service_account.terraform_gestion_patrimoine.email}"
}

resource "google_project_iam_member" "terraform_gestion_patrimoine_iam_admin" {
  project = var.project_id
  role    = "roles/resourcemanager.projectIamAdmin"
  member  = "serviceAccount:${google_service_account.terraform_gestion_patrimoine.email}"
}

resource "google_project_iam_member" "terraform_gestion_patrimoine_bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.terraform_gestion_patrimoine.email}"
}

resource "google_project_iam_member" "terraform_gestion_patrimoine_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.terraform_gestion_patrimoine.email}"
}

resource "google_project_iam_member" "terraform_gestion_patrimoine_storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.terraform_gestion_patrimoine.email}"
}

resource "google_project_iam_member" "terraform_gestion_patrimoine_key_admin" {
  project = var.project_id
  role    = "roles/iam.serviceAccountKeyAdmin"
  member  = "serviceAccount:${google_service_account.terraform_gestion_patrimoine.email}"
}

resource "google_service_account_key" "terraform_gestion_patrimoine_key" {
  service_account_id = google_service_account.terraform_gestion_patrimoine.name
}

# ─────────────────────────────────────────
# BigQuery Dataset
# ─────────────────────────────────────────

resource "google_bigquery_dataset" "referentiel_patrimoine" {
  dataset_id  = "referentiel_patrimoine"
  location    = var.bq_location
  description = "Référentiel juridique Gestion Patrimoine — articles du CGI collectés via l'API PISTE Légifrance (donations/successions, IFI, plus-values, assurance-vie, PER)"

  lifecycle {
    prevent_destroy = true
  }
}
