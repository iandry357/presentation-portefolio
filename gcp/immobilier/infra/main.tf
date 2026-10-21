terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "portfolio-emploi-tfstate"
    prefix = "gcp/immobilier/infra"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ─────────────────────────────────────────
# Service Account Pipeline
# ─────────────────────────────────────────

resource "google_service_account" "pipeline_immobilier" {
  account_id   = "pipeline-immobilier"
  display_name = "Pipeline Immobilier — ETL + BigQuery"
  description  = "Service account dédié au pipeline Immobilier (DPE ADEME + DVF, collecte, transformation, chargement BigQuery, lecture backend)"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "pipeline_immobilier_bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.pipeline_immobilier.email}"
}

resource "google_project_iam_member" "pipeline_immobilier_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.pipeline_immobilier.email}"
}

resource "google_service_account_key" "pipeline_immobilier_key" {
  service_account_id = google_service_account.pipeline_immobilier.name
}

# ─────────────────────────────────────────
# Service Account Terraform CI/CD
# ─────────────────────────────────────────

resource "google_service_account" "terraform_immobilier" {
  account_id   = "terraform-immobilier"
  display_name = "Terraform Immobilier — CI/CD GitHub Actions"
  description  = "Service account dédié Terraform CI/CD pour l'infra Immobilier"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "terraform_immobilier_sa_admin" {
  project = var.project_id
  role    = "roles/iam.serviceAccountAdmin"
  member  = "serviceAccount:${google_service_account.terraform_immobilier.email}"
}

resource "google_project_iam_member" "terraform_immobilier_iam_admin" {
  project = var.project_id
  role    = "roles/resourcemanager.projectIamAdmin"
  member  = "serviceAccount:${google_service_account.terraform_immobilier.email}"
}

resource "google_project_iam_member" "terraform_immobilier_bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.terraform_immobilier.email}"
}

resource "google_project_iam_member" "terraform_immobilier_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.terraform_immobilier.email}"
}

resource "google_project_iam_member" "terraform_immobilier_storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.terraform_immobilier.email}"
}

resource "google_project_iam_member" "terraform_immobilier_key_admin" {
  project = var.project_id
  role    = "roles/iam.serviceAccountKeyAdmin"
  member  = "serviceAccount:${google_service_account.terraform_immobilier.email}"
}

resource "google_service_account_key" "terraform_immobilier_key" {
  service_account_id = google_service_account.terraform_immobilier.name
}

# ─────────────────────────────────────────
# BigQuery Dataset
# ─────────────────────────────────────────

resource "google_bigquery_dataset" "immobilier" {
  dataset_id  = "immobilier"
  location    = var.bq_location
  description = "MVP Immobilier — DPE ADEME (Paris) et DVF Etalab (prix, agrégats)"

  lifecycle {
    prevent_destroy = true
  }
}
