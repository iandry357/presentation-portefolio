# Dockerfile — pipeline gestion-patrimoine
# Job batch (pas un service persistant) : collecte Légifrance -> chunking
# -> chargement BigQuery/ChromaDB. Exécuté via `docker-compose run --rm`.
#
# Build context : .. (racine du MVP gestion-patrimoine), pas pipeline/ —
# nécessaire pour que le package Python "pipeline" soit importable
# (from pipeline.xxx import ...) et pour que gcp_sa_gestion_patrimoine.json,
# à la racine du MVP, soit monté au bon endroit par docker-compose.yml.

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app

# Dépendances système minimales (certificats pour les appels HTTPS PISTE/GCP)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pipeline/requirements.txt .
COPY pipeline/constraints.txt .
RUN pip install --no-cache-dir -c constraints.txt -r requirements.txt

COPY pipeline/ ./pipeline/
COPY scripts/ ./scripts/

# gcp_sa_gestion_patrimoine.json et .env sont montés via volumes — jamais
# copiés dans l'image. Le script à exécuter (orchestrator.py, ou un
# collector/loader isolé pour du debug) est précisé dans docker-compose.yml
# ou passé en argument à `docker-compose run --rm pipeline python pipeline/<script>`.
ENTRYPOINT ["python"]
CMD ["pipeline/orchestrator.py"]