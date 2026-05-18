FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app

# Dépendances système minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code source
COPY pipeline/ ./pipeline/
COPY ml/ ./ml/

# Le .env et gcp_sa_sanofi.json sont montés via volumes — jamais copiés dans l'image

CMD ["python", "pipeline/orchestrator.py"]