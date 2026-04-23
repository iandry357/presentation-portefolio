# Les workflows GCP Workflows ne supportent pas terraform import
# Gérés manuellement via la console GCP
# À réactiver quand le provider hashicorp/google supportera l'import
# -------------------------------

# # Workflow trigger-sync-job — créé en Phase 2A, importé ici
# resource "google_workflows_workflow" "trigger_sync_job" {
#   name            = "trigger-sync-job"
#   region          = var.region
#   project         = var.project_id
#   service_account = google_service_account.pipeline_emploi.email

#   source_contents = <<-EOT
#     main:
#       steps:
#         - run_job:
#             call: http.post
#             args:
#               url: ${"https://europe-west9-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/gen-lang-client-0989575872/jobs/sync-ft-bigquery:run"}
#               auth:
#                 type: OAuth2
#             result: response
#         - return_result:
#             return: $${response.body}
#   EOT

#   lifecycle {
#     prevent_destroy = true
#   }

# }

# # Workflow trigger-explore-rome — créé en Phase 2A, importé ici
# resource "google_workflows_workflow" "trigger_explore_rome" {
#   name            = "trigger-explore-rome"
#   region          = var.region
#   project         = var.project_id
#   service_account = google_service_account.pipeline_emploi.email

#   source_contents = <<-EOT
#     main:
#       steps:
#         - run_job:
#             call: http.post
#             args:
#               url: ${"https://europe-west9-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/gen-lang-client-0989575872/jobs/sync-ft-bigquery:run"}
#               auth:
#                 type: OAuth2
#               body:
#                 overrides:
#                   containerOverrides:
#                     - env:
#                         - name: MODE
#                           value: explore_rome
#             result: response
#         - return_result:
#             return: $${response.body}
#   EOT

#   lifecycle {
#     prevent_destroy = true
#   }

# }

# import {
#   to = google_workflows_workflow.trigger_sync_job
#   id = "projects/gen-lang-client-0989575872/locations/europe-west9/workflows/trigger-sync-job"
# }

# import {
#   to = google_workflows_workflow.trigger_explore_rome
#   id = "projects/gen-lang-client-0989575872/locations/europe-west9/workflows/trigger-explore-rome"
# }