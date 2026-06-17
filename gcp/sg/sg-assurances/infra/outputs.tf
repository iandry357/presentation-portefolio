output "service_account_email" {
  description = "Email du service account pipeline-sg-assurances"
  value       = google_service_account.pipeline_sg.email
}

output "service_account_key" {
  description = "Clé JSON du service account pipeline-sg-assurances (base64)"
  value       = google_service_account_key.pipeline_sg_key.private_key
  sensitive   = true
}

output "terraform_sg_key" {
  description = "Clé JSON du service account terraform-sg-assurances (base64)"
  value       = google_service_account_key.terraform_sg_key.private_key
  sensitive   = true
}

output "bq_dataset_sg_assurance_veille" {
  description = "ID du dataset BigQuery sg_assurance_veille"
  value       = google_bigquery_dataset.sg_assurance_veille.dataset_id
}