# ============================================================
# PROTOCOLE DÉPLOIEMENT GCP — sync_job
# À lancer depuis : gcp/sync_job/
# ============================================================

# --- 1. BUILD --no-cache ---
docker build --no-cache -t europe-west9-docker.pkg.dev/gen-lang-client-0989575872/sync-job-registry/sync-job:latest .

# --- 2. PUSH vers Artifact Registry ---
docker push europe-west9-docker.pkg.dev/gen-lang-client-0989575872/sync-job-registry/sync-job:latest

# --- 3. UPDATE du Cloud Run Job ---
gcloud run jobs update sync-ft-bigquery --image europe-west9-docker.pkg.dev/gen-lang-client-0989575872/sync-job-registry/sync-job:latest --region europe-west9

# --- 4. RUN MANUEL de validation ---
gcloud run jobs execute sync-ft-bigquery --region europe-west9




# ============================================================
# LOCAL RUN GCP — sync_job
# À lancer depuis : gcp/sync_job/
# ============================================================
docker build --no-cache -t sync-job-local .

docker run --rm -v "%cd%\debug:/app/debug" --env-file .env.local sync-job-local