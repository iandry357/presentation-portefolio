# Secrets existants — créés en Phase 1/2B, importés ici
# Les versions (valeurs) sont gérées hors Terraform pour éviter
# de stocker des secrets sensibles dans le state

resource "google_secret_manager_secret" "ft_client_id" {
  secret_id = "ft-client-id"
  project   = var.project_id

  replication {
    auto {}
  }

  lifecycle {
    prevent_destroy = true
  }

}

resource "google_secret_manager_secret" "ft_client_secret" {
  secret_id = "ft-client-secret"
  project   = var.project_id

  replication {
    auto {}
  }
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_secret_manager_secret" "openai_api_key" {
  secret_id = "openai-api-key"
  project   = var.project_id

  replication {
    auto {}
  }

  lifecycle {
    prevent_destroy = true
  }

}

resource "google_secret_manager_secret" "gmail_credentials" {
  secret_id = "gmail-credentials"
  project   = var.project_id

  replication {
    auto {}
  }


  lifecycle {
    prevent_destroy = true
  }

}

resource "google_secret_manager_secret" "gmail_token" {
  secret_id = "gmail-token"
  project   = var.project_id

  replication {
    auto {}
  }


  lifecycle {
    prevent_destroy = true
  }

}