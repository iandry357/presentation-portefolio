# Service Account existant — créé en Phase 1, importé ici
resource "google_service_account" "pipeline_emploi" {
  account_id   = "pipeline-emploi"
  display_name = "Pipeline Emploi SA"
  project      = var.project_id

  lifecycle {
    prevent_destroy = true
  }

}

# ── Rôles IAM ─────────────────────────────────────────────────────────────────

locals {
  sa_roles = [
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
    "roles/run.invoker",
    "roles/run.developer",
    "roles/secretmanager.secretAccessor",
    "roles/storage.objectAdmin",
    "roles/pubsub.publisher",
    "roles/workflows.invoker",
    "roles/secretmanager.secretVersionManager",
  ]
}

resource "google_project_iam_member" "pipeline_emploi_roles" {
  for_each = toset(local.sa_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.pipeline_emploi.email}"
}