output "service_account_email" {
  description = "Email du service account pipeline-sanofi"
  value       = google_service_account.pipeline_sanofi.email
}

output "service_account_key" {
  description = "Clé JSON du service account (base64)"
  value       = google_service_account_key.pipeline_sanofi_key.private_key
  sensitive   = true
}

output "bq_dataset_clinical_trials" {
  description = "ID du dataset BigQuery sanofi_clinical_trials"
  value       = google_bigquery_dataset.sanofi_clinical_trials.dataset_id
}

output "bq_dataset_pubmed" {
  description = "ID du dataset BigQuery sanofi_pubmed"
  value       = google_bigquery_dataset.sanofi_pubmed.dataset_id
}

output "bq_dataset_news" {
  description = "ID du dataset BigQuery sanofi_news"
  value       = google_bigquery_dataset.sanofi_news.dataset_id
}

output "terraform_sanofi_key" {
  description = "Clé JSON du service account terraform-sanofi (base64)"
  value       = google_service_account_key.terraform_sanofi_key.private_key
  sensitive   = true
}