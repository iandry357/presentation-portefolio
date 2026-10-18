terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "portfolio-emploi-tfstate"
    prefix = "gcp/top-offres/infra"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ─────────────────────────────────────────
# BigQuery Dataset
# ─────────────────────────────────────────

resource "google_bigquery_dataset" "top_offres" {
  dataset_id  = "top_offres"
  location    = var.bq_location
  description = "Top Offres — classement quotidien des offres d'emploi (cibles, scoring LLM local, marts dbt)"

  lifecycle {
    prevent_destroy = true
  }
}

# ─────────────────────────────────────────
# Service Account Pipeline
# ─────────────────────────────────────────

resource "google_service_account" "pipeline_top_offres" {
  account_id   = "pipeline-top-offres"
  display_name = "Pipeline Top Offres — worker local + dbt"
  description  = "Service account du worker Top Offres (lecture emploi_marche et bucket de config, écriture top_offres uniquement)"

  lifecycle {
    prevent_destroy = true
  }
}

# Jobs BigQuery : niveau projet (obligatoire)
resource "google_project_iam_member" "pipeline_top_offres_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.pipeline_top_offres.email}"
}

# Écriture : dataset top_offres seul
resource "google_bigquery_dataset_iam_member" "pipeline_top_offres_editor" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.top_offres.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.pipeline_top_offres.email}"
}

# Lecture : dataset emploi_marche seul (aucune écriture)
resource "google_bigquery_dataset_iam_member" "pipeline_top_offres_source_viewer" {
  project    = var.project_id
  dataset_id = var.dataset_source_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.pipeline_top_offres.email}"
}

# Lecture : bucket de configuration seul
resource "google_storage_bucket_iam_member" "pipeline_top_offres_config_viewer" {
  bucket = var.config_bucket_name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.pipeline_top_offres.email}"
}

resource "google_service_account_key" "pipeline_top_offres_key" {
  service_account_id = google_service_account.pipeline_top_offres.name
}

# ─────────────────────────────────────────
# Service Account Terraform CI/CD
# ─────────────────────────────────────────

resource "google_service_account" "terraform_top_offres" {
  account_id   = "terraform-top-offres"
  display_name = "Terraform Top Offres — CI/CD GitHub Actions"
  description  = "Service account dédié Terraform CI/CD pour l'infra Top Offres"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "terraform_top_offres_sa_admin" {
  project = var.project_id
  role    = "roles/iam.serviceAccountAdmin"
  member  = "serviceAccount:${google_service_account.terraform_top_offres.email}"
}

resource "google_project_iam_member" "terraform_top_offres_iam_admin" {
  project = var.project_id
  role    = "roles/resourcemanager.projectIamAdmin"
  member  = "serviceAccount:${google_service_account.terraform_top_offres.email}"
}

resource "google_project_iam_member" "terraform_top_offres_bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.terraform_top_offres.email}"
}

resource "google_project_iam_member" "terraform_top_offres_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.terraform_top_offres.email}"
}

resource "google_project_iam_member" "terraform_top_offres_storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.terraform_top_offres.email}"
}

resource "google_project_iam_member" "terraform_top_offres_key_admin" {
  project = var.project_id
  role    = "roles/iam.serviceAccountKeyAdmin"
  member  = "serviceAccount:${google_service_account.terraform_top_offres.email}"
}

resource "google_service_account_key" "terraform_top_offres_key" {
  service_account_id = google_service_account.terraform_top_offres.name
}
