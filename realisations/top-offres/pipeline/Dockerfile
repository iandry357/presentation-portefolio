# Dockerfile — pipeline top-offres
# Worker batch local (PC Windows) : collecte, scoring LLM via Ollama, dbt.
# Exécuté via `docker-compose run --rm`, jamais en service persistant.
#
# Build context : .. (racine du MVP top-offres), pas pipeline/ — nécessaire pour
# copier agents/ et dbt/ (hors de pipeline/) et pour monter la clé
# gcp_sa_top_offres.json, à la racine du MVP.

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Dépendances système minimales (certificats pour les appels HTTPS)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pipeline/requirements.txt .
COPY pipeline/constraints.txt .
RUN pip install --no-cache-dir -c constraints.txt -r requirements.txt

COPY pipeline/ ./pipeline/
COPY agents/ ./agents/
COPY dbt/ ./dbt/
COPY scripts/ ./scripts/

# .env, gcp_sa_top_offres.json et results/ sont montés via docker-compose.yml —
# jamais copiés dans l'image.
ENTRYPOINT ["python"]
CMD ["pipeline/orchestrator.py"]
