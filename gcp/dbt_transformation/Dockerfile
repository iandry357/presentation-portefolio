# ============================================================
# gcp/dbt_transformation/Dockerfile
# Image du Cloud Run Job de transformation emploi_marche
# ============================================================

FROM python:3.11-slim

# git requis par certaines dépendances internes de dbt (packages Hub)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /dbt

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dbt_project.yml .
COPY profiles.yml .
COPY models/ ./models/
COPY tests/ ./tests/
COPY entrypoint.sh .
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

# dbt cherche profiles.yml dans ~/.dbt/ par défaut — on le redirige
# explicitement vers le répertoire du projet où on vient de le copier.
ENV DBT_PROFILES_DIR=/dbt

ENTRYPOINT ["./entrypoint.sh"]