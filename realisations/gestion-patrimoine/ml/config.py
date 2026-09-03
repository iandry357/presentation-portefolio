"""
config.py — Constantes de configuration pour l'image ml-service (port 8008)
du MVP gestion-patrimoine.

Image Docker indépendante de pipeline/ : ce fichier ne dépend d'aucun import
provenant de pipeline/config.py, il duplique volontairement les constantes
nécessaires à ce contexte d'exécution (cohérent avec le fait que ml/ est
buildé et déployé séparément).

Toutes les valeurs sont lues depuis l'environnement. Celles qui n'ont pas de
valeur par défaut raisonnable (secrets, hôtes) lèvent une erreur explicite si
absentes plutôt que de démarrer avec une configuration silencieusement fausse.
"""

import os

# --------------------------------------------------------------------------
# ChromaDB
# --------------------------------------------------------------------------

CHROMA_HOST = os.environ["CHROMA_HOST"]
CHROMA_PORT = int(os.environ["CHROMA_PORT"])
CHROMA_USER = os.environ["CHROMA_USER"]
CHROMA_PASSWORD = os.environ["CHROMA_PASSWORD"]
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "referentiel_patrimoine")

# --------------------------------------------------------------------------
# Embedding-service partagé (port 8004, wake-on-demand)
# --------------------------------------------------------------------------

EMBEDDING_SERVICE_URL = os.environ["EMBEDDING_SERVICE_URL"]
EMBEDDING_SERVICE_KEY = os.getenv("EMBEDDING_SERVICE_KEY", "embedding-service")

# --------------------------------------------------------------------------
# Orchestrateur OVH (wake-on-demand)
# --------------------------------------------------------------------------

OVH_ORCHESTRATOR_URL = os.environ["OVH_ORCHESTRATOR_URL"]
WAKE_TIMEOUT_SEC = int(os.getenv("WAKE_TIMEOUT_SEC", "60"))
WAKE_POLL_INTERVAL_SEC = int(os.getenv("WAKE_POLL_INTERVAL_SEC", "2"))

# --------------------------------------------------------------------------
# Recherche vectorielle
# --------------------------------------------------------------------------

SEARCH_TOP_K = int(os.getenv("SEARCH_TOP_K", "3"))

# --------------------------------------------------------------------------
# llama-server (Qwen2.5-Instruct GGUF, systemd, hors orchestrateur)
# --------------------------------------------------------------------------

LLAMA_SERVER_URL = os.environ["LLAMA_SERVER_URL"]  # ex: http://172.x.x.1:PORT/v1/chat/completions
LLAMA_MAX_TOKENS = int(os.getenv("LLAMA_MAX_TOKENS", "400"))
LLAMA_TIMEOUT_SEC = float(os.getenv("LLAMA_TIMEOUT_SEC", "120.0"))