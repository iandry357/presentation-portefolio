terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "portfolio-emploi-tfstate"
    prefix = "gcp/sanofi/infra"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ─────────────────────────────────────────
# Service Account
# ─────────────────────────────────────────

resource "google_service_account" "pipeline_sanofi" {
  account_id   = "pipeline-sanofi"
  display_name = "Pipeline Sanofi — ETL + BigQuery"
  description  = "Service account dédié au pipeline ETL Sanofi (collecte, transformation, chargement BigQuery)"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "pipeline_sanofi_bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.pipeline_sanofi.email}"
}

resource "google_project_iam_member" "pipeline_sanofi_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.pipeline_sanofi.email}"
}

resource "google_service_account_key" "pipeline_sanofi_key" {
  service_account_id = google_service_account.pipeline_sanofi.name
}

# ─────────────────────────────────────────
# Service Account Terraform CI/CD
# ─────────────────────────────────────────

resource "google_service_account" "terraform_sanofi" {
  account_id   = "terraform-sanofi"
  display_name = "Terraform Sanofi — CI/CD GitHub Actions"
  description  = "Service account dédié Terraform CI/CD pour l'infra Sanofi"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "terraform_sanofi_sa_admin" {
  project = var.project_id
  role    = "roles/iam.serviceAccountAdmin"
  member  = "serviceAccount:${google_service_account.terraform_sanofi.email}"
}

resource "google_project_iam_member" "terraform_sanofi_iam_admin" {
  project = var.project_id
  role    = "roles/resourcemanager.projectIamAdmin"
  member  = "serviceAccount:${google_service_account.terraform_sanofi.email}"
}

resource "google_project_iam_member" "terraform_sanofi_bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.terraform_sanofi.email}"
}

resource "google_project_iam_member" "terraform_sanofi_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.terraform_sanofi.email}"
}

resource "google_project_iam_member" "terraform_sanofi_storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.terraform_sanofi.email}"
}

resource "google_service_account_key" "terraform_sanofi_key" {
  service_account_id = google_service_account.terraform_sanofi.name
}

# ─────────────────────────────────────────
# BigQuery Datasets
# ─────────────────────────────────────────

resource "google_bigquery_dataset" "sanofi_clinical_trials" {
  dataset_id  = "sanofi_clinical_trials"
  location    = var.bq_location
  description = "Essais cliniques Sanofi — ClinicalTrials.gov API v2"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_bigquery_dataset" "sanofi_pubmed" {
  dataset_id  = "sanofi_pubmed"
  location    = var.bq_location
  description = "Publications R&D Sanofi — PubMed API"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_bigquery_dataset" "sanofi_news" {
  dataset_id  = "sanofi_news"
  location    = var.bq_location
  description = "Actualités Sanofi — Google News RSS"

  lifecycle {
    prevent_destroy = true
  }
}