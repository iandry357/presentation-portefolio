FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime

# Variables d'environnement
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    MODEL_TYPE=base \
    GCS_BASE_MODEL_URI=gs://sg-assurances-models/sg-assurances/qwen-base \
    GCS_FINETUNED_URI=gs://sg-assurances-models/sg-assurances/qlora/qlora_sg_assurances \
    LOCAL_BASE_CACHE=/app/models/qwen-base \
    LOCAL_FINETUNED_CACHE=/app/models/qlora

# Installer gsutil + dépendances système
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    && echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] http://packages.cloud.google.com/apt cloud-sdk main" \
    | tee /etc/apt/sources.list.d/google-cloud-sdk.list \
    && curl https://packages.cloud.google.com/apt/doc/apt-key.gpg \
    | apt-key --keyring /usr/share/keyrings/cloud.google.gpg add - \
    && apt-get update && apt-get install -y google-cloud-cli \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installer dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code applicatif
COPY main.py .

# Répertoires modèles
RUN mkdir -p /app/models/qwen-base /app/models/qlora

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]