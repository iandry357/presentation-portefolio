output "service_account_email" {
  description = "Email du service account pipeline-immobilier"
  value       = google_service_account.pipeline_immobilier.email
}

output "service_account_key" {
  description = "Clé JSON du service account pipeline-immobilier (base64)"
  value       = google_service_account_key.pipeline_immobilier_key.private_key
  sensitive   = true
}

output "terraform_immobilier_key" {
  description = "Clé JSON du service account terraform-immobilier (base64)"
  value       = google_service_account_key.terraform_immobilier_key.private_key
  sensitive   = true
}

output "bq_dataset_immobilier" {
  description = "ID du dataset BigQuery immobilier"
  value       = google_bigquery_dataset.immobilier.dataset_id
}
