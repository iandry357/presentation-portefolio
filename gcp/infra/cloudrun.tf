# Cloud Run Job — créé en Phase 2A, importé ici
resource "google_cloud_run_v2_job" "sync_job" {
  name     = "sync-ft-bigquery"
  location = var.region
  project  = var.project_id

  template {
    template {
      service_account = google_service_account.pipeline_emploi.email

      max_retries = 3

      timeout = "600s"

      containers {
        image = var.sync_job_image

        env {
          name  = "BQ_PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "BQ_DATASET"
          value = "emploi_marche"
        }
        env {
          name  = "BQ_TABLE"
          value = "offres_brutes"
        }
        env {
          name  = "GCS_BUCKET"
          value = google_storage_bucket.config.name
        }
        env {
          name  = "MODE"
          value = "sync"
        }

        # Secrets injectés depuis Secret Manager
        env {
          name = "FT_CLIENT_ID"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.ft_client_id.secret_id
              version = "latest"
            }
          }
        }
        env {
          name = "FT_CLIENT_SECRET"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.ft_client_secret.secret_id
              version = "latest"
            }
          }
        }
        env {
          name = "OPENAI_API_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.openai_api_key.secret_id
              version = "latest"
            }
          }
        }
        env {
          name = "GMAIL_CREDENTIALS_JSON"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.gmail_credentials.secret_id
              version = "latest"
            }
          }
        }
        env {
          name = "GMAIL_TOKEN_JSON"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.gmail_token.secret_id
              version = "latest"
            }
          }
        }

        env {
            name  = "BOOTSTRAP_MODE"
            value = "false"
        }
        env {
            name  = "REGION"
            value = "11"
        }

        resources {
          limits = {
            cpu    = "1000m"
            memory = "512Mi"
          }
        }
      }
    }
  }

  lifecycle {
    prevent_destroy = true
  }

}