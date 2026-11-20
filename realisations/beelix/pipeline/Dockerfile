FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Dépendances Python
COPY pipeline/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code source
COPY pipeline/ ./pipeline/

# Le .env et gcp_sa_sg.json sont montés (env_file, volume) — jamais copiés dans l'image (.dockerignore)

CMD ["python", "pipeline/orchestrator.py"]
