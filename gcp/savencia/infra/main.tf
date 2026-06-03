terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "portfolio-emploi-tfstate"
    prefix = "gcp/savencia/infra"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ─────────────────────────────────────────
# Service Account Pipeline
# ─────────────────────────────────────────

resource "google_service_account" "pipeline_savencia" {
  account_id   = "pipeline-savencia"
  display_name = "Pipeline Savencia — ETL + BigQuery"
  description  = "Service account dédié au pipeline ETL Savencia (collecte, transformation, chargement BigQuery)"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "pipeline_savencia_bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.pipeline_savencia.email}"
}

resource "google_project_iam_member" "pipeline_savencia_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.pipeline_savencia.email}"
}

resource "google_service_account_key" "pipeline_savencia_key" {
  service_account_id = google_service_account.pipeline_savencia.name
}

# ─────────────────────────────────────────
# Service Account Terraform CI/CD
# ─────────────────────────────────────────

resource "google_service_account" "terraform_savencia" {
  account_id   = "terraform-savencia"
  display_name = "Terraform Savencia — CI/CD GitHub Actions"
  description  = "Service account dédié Terraform CI/CD pour l'infra Savencia"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "terraform_savencia_sa_admin" {
  project = var.project_id
  role    = "roles/iam.serviceAccountAdmin"
  member  = "serviceAccount:${google_service_account.terraform_savencia.email}"
}

resource "google_project_iam_member" "terraform_savencia_iam_admin" {
  project = var.project_id
  role    = "roles/resourcemanager.projectIamAdmin"
  member  = "serviceAccount:${google_service_account.terraform_savencia.email}"
}

resource "google_project_iam_member" "terraform_savencia_bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.terraform_savencia.email}"
}

resource "google_project_iam_member" "terraform_savencia_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.terraform_savencia.email}"
}

resource "google_project_iam_member" "terraform_savencia_storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.terraform_savencia.email}"
}

resource "google_service_account_key" "terraform_savencia_key" {
  service_account_id = google_service_account.terraform_savencia.name
}

resource "google_project_iam_member" "terraform_savencia_key_admin" {
  project = var.project_id
  role    = "roles/iam.serviceAccountKeyAdmin"
  member  = "serviceAccount:${google_service_account.terraform_savencia.email}"
}

resource "google_project_iam_member" "terraform_savencia_storage_bucket_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.terraform_savencia.email}"
}

# ─────────────────────────────────────────
# BigQuery Dataset
# ─────────────────────────────────────────

resource "google_bigquery_dataset" "savencia_veille" {
  dataset_id  = "savencia_veille"
  location    = var.bq_location
  description = "Veille stratégique Savencia — Google News RSS"

  lifecycle {
    prevent_destroy = true
  }
}

# ─────────────────────────────────────────
# GCS Bucket — Artefacts modèles
# ─────────────────────────────────────────

resource "google_storage_bucket" "savencia_models" {
  name          = "savencia-models"
  location      = "EU"
  force_destroy = false

  versioning {
    enabled = true
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_storage_bucket_iam_member" "pipeline_savencia_storage_reader" {
  bucket = google_storage_bucket.savencia_models.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.pipeline_savencia.email}"
}

resource "google_storage_bucket_iam_member" "pipeline_savencia_storage_writer" {
  bucket = google_storage_bucket.savencia_models.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.pipeline_savencia.email}"
}