locals {
  secrets = {
    GEMINI_API_KEY               = var.gemini_api_key
    SECRET_KEY                   = var.secret_key
    MISTRAL_API_KEY              = var.mistral_api_key
    GROQ_API_KEY                 = var.groq_api_key
    LANGSMITH_API_KEY            = var.langsmith_api_key
    VOYAGE_API_KEY               = var.voyage_api_key
    FRANCE_TRAVAIL_CLIENT_ID     = var.france_travail_client_id
    FRANCE_TRAVAIL_CLIENT_SECRET = var.france_travail_client_secret
    DATABASE_URL                 = var.database_url
    OPENAI_API_KEY               = var.openai_api_key
    POSTGRES_PASSWORD            = var.postgres_password
    SERPER_API_KEY               = var.serper_api_key
  }
}

resource "scaleway_secret" "main" {
  for_each   = local.secrets
  name       = each.key
  project_id = var.project_id
  region     = var.region
}

resource "scaleway_secret_version" "main" {
  for_each  = local.secrets
  secret_id = scaleway_secret.main[each.key].id
  data      = each.value
}