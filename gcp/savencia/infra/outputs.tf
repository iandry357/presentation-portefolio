output "service_account_email" {
  description = "Email du service account pipeline-savencia"
  value       = google_service_account.pipeline_savencia.email
}

output "service_account_key" {
  description = "Clé JSON du service account pipeline-savencia (base64)"
  value       = google_service_account_key.pipeline_savencia_key.private_key
  sensitive   = true
}

output "terraform_savencia_key" {
  description = "Clé JSON du service account terraform-savencia (base64)"
  value       = google_service_account_key.terraform_savencia_key.private_key
  sensitive   = true
}

output "bq_dataset_savencia_veille" {
  description = "ID du dataset BigQuery savencia_veille"
  value       = google_bigquery_dataset.savencia_veille.dataset_id
}

output "savencia_models_bucket" {
  description = "Bucket GCS artefacts modèles Savencia"
  value       = google_storage_bucket.savencia_models.name
}