# Build context attendu : .. (racine du MVP gestion-patrimoine)
# Nécessaire pour copier agents/ en package frère de ml/ (cf. imports
# agents.assistant_agent dans ml/main.py et ml.config dans agents/tools.py
# et agents/assistant_agent.py).

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

COPY ml/requirements.txt ./ml/requirements.txt
RUN pip install --no-cache-dir -r ml/requirements.txt

COPY agents/ ./agents/
COPY ml/ ./ml/

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8008/health || exit 1

EXPOSE 8008

CMD ["uvicorn", "ml.main:app", "--host", "0.0.0.0", "--port", "8008"]
