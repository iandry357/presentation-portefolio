terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "portfolio-emploi-tfstate"
    prefix = "gcp/sg/sg-assurances/infra"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ─────────────────────────────────────────
# Service Account Pipeline
# ─────────────────────────────────────────

resource "google_service_account" "pipeline_sg" {
  account_id   = "pipeline-sg-assurances"
  display_name = "Pipeline SG Assurances — ETL + BigQuery"
  description  = "Service account dédié au pipeline ETL SG Assurances (collecte, transformation, chargement BigQuery)"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "pipeline_sg_bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.pipeline_sg.email}"
}

resource "google_project_iam_member" "pipeline_sg_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.pipeline_sg.email}"
}

resource "google_service_account_key" "pipeline_sg_key" {
  service_account_id = google_service_account.pipeline_sg.name
}

# ─────────────────────────────────────────
# Service Account Terraform CI/CD
# ─────────────────────────────────────────

resource "google_service_account" "terraform_sg" {
  account_id   = "terraform-sg-assurances"
  display_name = "Terraform SG Assurances — CI/CD GitHub Actions"
  description  = "Service account dédié Terraform CI/CD pour l'infra SG Assurances"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "terraform_sg_sa_admin" {
  project = var.project_id
  role    = "roles/iam.serviceAccountAdmin"
  member  = "serviceAccount:${google_service_account.terraform_sg.email}"
}

resource "google_project_iam_member" "terraform_sg_iam_admin" {
  project = var.project_id
  role    = "roles/resourcemanager.projectIamAdmin"
  member  = "serviceAccount:${google_service_account.terraform_sg.email}"
}

resource "google_project_iam_member" "terraform_sg_bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.terraform_sg.email}"
}

resource "google_project_iam_member" "terraform_sg_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.terraform_sg.email}"
}

resource "google_project_iam_member" "terraform_sg_storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.terraform_sg.email}"
}

resource "google_project_iam_member" "terraform_sg_key_admin" {
  project = var.project_id
  role    = "roles/iam.serviceAccountKeyAdmin"
  member  = "serviceAccount:${google_service_account.terraform_sg.email}"
}

resource "google_service_account_key" "terraform_sg_key" {
  service_account_id = google_service_account.terraform_sg.name
}

# ─────────────────────────────────────────
# BigQuery Dataset
# ─────────────────────────────────────────

resource "google_bigquery_dataset" "sg_assurance_veille" {
  dataset_id  = "sg_assurance_veille"
  location    = var.bq_location
  description = "Veille stratégique SG Assurances — Google News RSS + PDFs"

  lifecycle {
    prevent_destroy = true
  }
}