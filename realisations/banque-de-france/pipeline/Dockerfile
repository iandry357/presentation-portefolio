# syntax=docker/dockerfile:1.4
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app

# Dépendances système minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY pipeline/requirements.txt .
COPY pipeline/constraints.txt .
RUN pip install --no-cache-dir torch==2.2.2 torchvision==0.17.2 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -c constraints.txt -r requirements.txt

RUN --mount=type=cache,target=/root/.cache/huggingface \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')"

# Code source
COPY pipeline/ ./pipeline/
COPY scripts/ ./scripts/

# Le .env et gcp_sa_banque.json sont montés via volumes — jamais copiés dans l'image

CMD ["python", "pipeline/orchestrator.py"]