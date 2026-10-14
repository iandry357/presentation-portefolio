output "service_account_email" {
  description = "Email du service account pipeline-top-offres"
  value       = google_service_account.pipeline_top_offres.email
}

output "service_account_key" {
  description = "Clé JSON du service account pipeline-top-offres (base64)"
  value       = google_service_account_key.pipeline_top_offres_key.private_key
  sensitive   = true
}

output "terraform_top_offres_key" {
  description = "Clé JSON du service account terraform-top-offres (base64)"
  value       = google_service_account_key.terraform_top_offres_key.private_key
  sensitive   = true
}

output "bq_dataset_top_offres" {
  description = "ID du dataset BigQuery top_offres"
  value       = google_bigquery_dataset.top_offres.dataset_id
}
