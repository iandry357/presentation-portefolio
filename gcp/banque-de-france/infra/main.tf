terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "portfolio-emploi-tfstate"
    prefix = "gcp/banque-de-france/infra"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ─────────────────────────────────────────
# Service Account Pipeline
# ─────────────────────────────────────────

resource "google_service_account" "pipeline_banque" {
  account_id   = "pipeline-banque-de-france"
  display_name = "Pipeline Banque de France — ETL + BigQuery"
  description  = "Service account dédié au pipeline ETL Banque de France (veille + ACPR, collecte, transformation, chargement BigQuery)"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "pipeline_banque_bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.pipeline_banque.email}"
}

resource "google_project_iam_member" "pipeline_banque_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.pipeline_banque.email}"
}

resource "google_service_account_key" "pipeline_banque_key" {
  service_account_id = google_service_account.pipeline_banque.name
}

# ─────────────────────────────────────────
# Service Account Terraform CI/CD
# ─────────────────────────────────────────

resource "google_service_account" "terraform_banque" {
  account_id   = "terraform-banque-de-france"
  display_name = "Terraform Banque de France — CI/CD GitHub Actions"
  description  = "Service account dédié Terraform CI/CD pour l'infra Banque de France"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "terraform_banque_sa_admin" {
  project = var.project_id
  role    = "roles/iam.serviceAccountAdmin"
  member  = "serviceAccount:${google_service_account.terraform_banque.email}"
}

resource "google_project_iam_member" "terraform_banque_iam_admin" {
  project = var.project_id
  role    = "roles/resourcemanager.projectIamAdmin"
  member  = "serviceAccount:${google_service_account.terraform_banque.email}"
}

resource "google_project_iam_member" "terraform_banque_bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.terraform_banque.email}"
}

resource "google_project_iam_member" "terraform_banque_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.terraform_banque.email}"
}

resource "google_project_iam_member" "terraform_banque_storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.terraform_banque.email}"
}

resource "google_project_iam_member" "terraform_banque_key_admin" {
  project = var.project_id
  role    = "roles/iam.serviceAccountKeyAdmin"
  member  = "serviceAccount:${google_service_account.terraform_banque.email}"
}

resource "google_service_account_key" "terraform_banque_key" {
  service_account_id = google_service_account.terraform_banque.name
}

# ─────────────────────────────────────────
# BigQuery Dataset
# ─────────────────────────────────────────

resource "google_bigquery_dataset" "banque_de_france_veille" {
  dataset_id  = "banque_de_france_veille"
  location    = var.bq_location
  description = "Veille stratégique Banque de France / ACPR — Google News RSS + Trafilatura + décisions ACPR"

  lifecycle {
    prevent_destroy = true
  }
}
