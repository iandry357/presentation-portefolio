#locals {
#  workflow_sync_uri         = "https://workflowexecutions.googleapis.com/v1/projects/${var.project_id}/locations/${var.region}/workflows/${google_workflows_workflow.trigger_sync_job.name}/executions"
#  workflow_explore_rome_uri = "https://workflowexecutions.googleapis.com/v1/projects/${var.project_id}/locations/${var.region}/workflows/${google_workflows_workflow.trigger_explore_rome.name}/executions"
#}

locals {
  workflow_sync_uri         = "https://workflowexecutions.googleapis.com/v1/projects/gen-lang-client-0989575872/locations/europe-west9/workflows/trigger-sync-job/executions"
  workflow_explore_rome_uri = "https://workflowexecutions.googleapis.com/v1/projects/gen-lang-client-0989575872/locations/europe-west9/workflows/trigger-explore-rome/executions"
}

# ── Sync quotidien ────────────────────────────────────────────────────────────

resource "google_cloud_scheduler_job" "sync_matin" {
  name      = "scheduler-sync-matin"
  project   = var.project_id
  region    = "europe-west1"
  schedule  = "0 7 * * *"
  time_zone = "Europe/Paris"

  retry_config {
    max_backoff_duration = "3600s"
    max_doublings        = 5
    max_retry_duration   = "0s"
    min_backoff_duration = "5s"
  }

  http_target {
    http_method = "POST"
    uri         = local.workflow_sync_uri

    oauth_token {
      service_account_email = google_service_account.pipeline_emploi.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}

resource "google_cloud_scheduler_job" "sync_midi" {
  name      = "scheduler-sync-midi"
  project   = var.project_id
  region    = "europe-west1"
  schedule  = "0 12 * * *"
  time_zone = "Europe/Paris"

  retry_config {
    max_backoff_duration = "3600s"
    max_doublings        = 5
    max_retry_duration   = "0s"
    min_backoff_duration = "5s"
  }

  http_target {
    http_method = "POST"
    uri         = local.workflow_sync_uri

    oauth_token {
      service_account_email = google_service_account.pipeline_emploi.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}

# ── Exploration ROME — 1er et 15 du mois ─────────────────────────────────────

resource "google_cloud_scheduler_job" "explore_rome" {
  name      = "scheduler-explore-rome"
  project   = var.project_id
  region    = "europe-west1"
  schedule  = "0 8 1,15 * *"
  time_zone = "Europe/Paris"

  retry_config {
    max_backoff_duration = "3600s"
    max_doublings        = 5
    max_retry_duration   = "0s"
    min_backoff_duration = "5s"
  }

  http_target {
    http_method = "POST"
    uri         = local.workflow_explore_rome_uri

    oauth_token {
      service_account_email = google_service_account.pipeline_emploi.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}