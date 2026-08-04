output "service_account_email" {
  description = "Email du service account pipeline-banque-de-france"
  value       = google_service_account.pipeline_banque.email
}

output "service_account_key" {
  description = "Clé JSON du service account pipeline-banque-de-france (base64)"
  value       = google_service_account_key.pipeline_banque_key.private_key
  sensitive   = true
}

output "terraform_banque_key" {
  description = "Clé JSON du service account terraform-banque-de-france (base64)"
  value       = google_service_account_key.terraform_banque_key.private_key
  sensitive   = true
}

output "bq_dataset_banque_de_france_veille" {
  description = "ID du dataset BigQuery banque_de_france_veille"
  value       = google_bigquery_dataset.banque_de_france_veille.dataset_id
}
