output "dbt_service_account_email" {
  description = "Email du SA pipeline-dbt — à utiliser dans profiles.yml (impersonate_service_account) et dans la config du Cloud Run Job (--service-account)"
  value       = google_service_account.pipeline_dbt.email
}
