FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Dépendances Python
COPY pipeline/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code source
COPY pipeline/ ./pipeline/

# Le .env et gcp_sa_sg.json sont montés via volumes — jamais copiés dans l'image
# ml/ est monté via volume (topic_modeling.py, résultats sur le disque hôte)

CMD ["python", "pipeline/orchestrator.py"]
