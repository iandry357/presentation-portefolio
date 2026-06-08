FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app

# Dépendances système minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir torch==2.2.2 --extra-index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Code source
COPY pipeline/ ./pipeline/
COPY scripts/ ./scripts/

# Le .env et gcp_sa_sg.json sont montés via volumes — jamais copiés dans l'image

CMD ["python", "pipeline/orchestrator.py"]