output "cloud_run_job_name" {
  description = "Nom du Cloud Run Job"
  value       = google_cloud_run_v2_job.sync_job.name
}

output "scheduler_sync_7h" {
  description = "ID scheduler sync 7h"
  value       = google_cloud_scheduler_job.sync_matin.name
}

output "scheduler_sync_12h" {
  description = "ID scheduler sync 12h"
  value       = google_cloud_scheduler_job.sync_midi.name
}


output "scheduler_explore_rome" {
  description = "ID scheduler explore ROME"
  value       = google_cloud_scheduler_job.explore_rome.name
}

output "bigquery_table" {
  description = "Référence complète table BigQuery"
  value       = "${var.project_id}.${google_bigquery_dataset.emploi_marche.dataset_id}.${google_bigquery_table.offres_brutes.table_id}"
}

output "config_bucket" {
  description = "Bucket GCS configuration"
  value       = google_storage_bucket.config.name
}