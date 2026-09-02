output "service_account_email" {
  description = "Email du service account pipeline-gestion-patrimoine"
  value       = google_service_account.pipeline_gestion_patrimoine.email
}

output "service_account_key" {
  description = "Clé JSON du service account pipeline-gestion-patrimoine (base64)"
  value       = google_service_account_key.pipeline_gestion_patrimoine_key.private_key
  sensitive   = true
}

output "terraform_gestion_patrimoine_key" {
  description = "Clé JSON du service account terraform-gestion-patrimoine (base64)"
  value       = google_service_account_key.terraform_gestion_patrimoine_key.private_key
  sensitive   = true
}

output "bq_dataset_referentiel_patrimoine" {
  description = "ID du dataset BigQuery referentiel_patrimoine"
  value       = google_bigquery_dataset.referentiel_patrimoine.dataset_id
}
