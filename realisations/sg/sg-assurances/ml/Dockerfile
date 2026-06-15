FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PORT=8003 \
    YOLO_MODEL_PATH=/app/models/yolo_sg_assurances.pt \
    NER_MODEL_PATH=/app/models/ner_sg_assurances \
    SA_KEY_PATH=/app/gcp_sa_sg.json \
    ENDPOINT_INFO_PATH=/app/models/qwen_endpoint_id.json

# Dépendances système + gsutil
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libgl1 \
    libglib2.0-0 \
    curl \
    gnupg \
    apt-transport-https \
    ca-certificates \
    && curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \
    | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
    > /etc/apt/sources.list.d/google-cloud-sdk.list \
    && apt-get update && apt-get install -y google-cloud-cli \
    && rm -rf /var/lib/apt/lists/*

# Torch CPU en premier — évite réinstallation GPU par dépendances transitives
RUN pip install --no-cache-dir \
    torch==2.1.0+cpu \
    torchvision==0.16.0+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# NumPy verrouillé avant les autres dépendances
RUN pip install --no-cache-dir numpy==1.26.4

# Dépendances applicatives — constraints verrouille torch CPU et numpy
COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir -c constraints.txt -r requirements.txt

# Code source
COPY *.py ./

# Répertoire modèles — rempli via volume au runtime
RUN mkdir -p /app/models

# gcp_sa_sg.json et modèles montés via volumes — jamais copiés dans l'image

EXPOSE 8003

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]