# Release 2 Sanofi — Bloc B : Graph RAG + LLM Fine-tuné
## Documentation de reproductibilité

---

## Résultat final

| Métrique | Valeur |
|---|---|
| Modèle | Mistral 7B Instruct v0.3 — QLoRA checkpoint-346 |
| Win-rate vs base | **46.7%** (seuil 30% — ✅ VALIDÉ) |
| Évaluation | 15 questions (8 EN / 7 FR), juge Gemma 3 12B |
| GGUF quantisé | Q4_K_M, 4.1 Go, llama-server port 8006 |
| Neo4j | 11 clusters, 11 721 targets, 158 261 relations |
| Débit inférence | ~5 tokens/sec CPU OVH |
| Vertex AI | `projects/870096195586/locations/europe-west9/models/18264119590382469121` |
| GCS | `gs://sanofi-models/sanofi/mistral7b-drug-discovery/` |

---

## Architecture finale

```
therapeutic_insight.json (résultats/sanofi/ml/results/)
    │
    ├── pipeline_orchestrator.py --skip-therapeutic
    │       └── neo4j_ingestion.py ──► Neo4j (sanofi-ml-network, port 7687)
    │                                  gateway: 172.21.0.1
    │
    └── training/
        finetune.py ──► models/lora/checkpoint-346/
        export_gguf.py ──► models/merged/ (27 Go float32)
        evaluate.py ──► models/eval_results.json (46.7%)
        register_model.py ──► GCS + Vertex AI
            │
            convert_hf_to_gguf.py (local, sg/llama.cpp/)
            ──► mistral7b-drug-f16.gguf (local, 14 Go)
            scp ──► OVH ml/models/
            llama-quantize (OVH) ──► mistral7b-drug.gguf (4.1 Go)
            llama-server-sanofi.service (port 8006, -c 2048)
                    │
                graph_rag.py (ml-service port 8001)
                LLAMA_SERVER_URL = http://172.21.0.1:8006
                3 signaux Cypher (LIMIT 3) + contexte ~4200 chars
                LLAMA_TIMEOUT = 180s
                    │
            POST /sanofi/ml/graph-rag (backend Scaleway, timeout 180s)
                    │
            ClusteringView.tsx — encart Q&A + questions profil + progress bar
```

---

## Étape 1 — Fine-tuning Mistral 7B (local, RTX 5060)

### Prérequis
- `venv-sanofi` activé
- `training/data/dataset_train.jsonl` (2768 exemples) + `dataset_eval.jsonl` (692)
- Si datasets absents : `python prepare_dataset.py` d'abord

### Commande
```
cd realisations\sanofi\training
python finetune.py
```

### Durée
~216 minutes (3h36) sur RTX 5060 8GB.

### Résultats attendus
```
models/lora/
    ├── checkpoint-173/   (epoch 1)
    ├── checkpoint-346/   (epoch 2) ← meilleur checkpoint
    ├── checkpoint-519/   (epoch 3)
    └── finetune_metrics.json
models/checkpoints_history.json  ← généré automatiquement
```

### Métriques obtenues (run de référence)
| Epoch | Checkpoint | eval_loss | eval_mean_token_accuracy |
|---|---|---|---|
| 1 | checkpoint-173 | 1.4209 | 0.6548 |
| **2** | **checkpoint-346** | **1.4226** | **0.6549** ← sélectionné |
| 3 | checkpoint-519 | 1.4730 | 0.6506 |

### ⚠️ Problèmes rencontrés
| Problème | Cause | Fix |
|---|---|---|
| `train_loss=5.188` en fin de run | Moyenne glissante HF Trainer sur tout l'entraînement — pas la loss finale | Normal, ignorer — regarder `eval_loss` uniquement |
| Epoch 3 décroche vs epoch 2 | Légère sur-adaptation à partir d'epoch 3 | Sélectionner checkpoint-346 (epoch 2) |
| `finetune.py` ne sauvegardait pas le meilleur checkpoint à la racine | `load_best_model_at_end=True` ne persiste qu'en mémoire | Ajout de `_save_checkpoints_history()` + lecture via `checkpoints_history.json` |

---

## Étape 2 — Export merge LoRA (local)

### Prérequis
- `models/lora/checkpoint-346/` présent
- `models/checkpoints_history.json` présent

### Commande
```
cd realisations\sanofi\training
python export_gguf.py
```

### Ce que le script fait
1. Lit `checkpoints_history.json` → sélectionne checkpoint-346 automatiquement (meilleure accuracy)
2. Merge LoRA + modèle base → `models/merged/` (6 fichiers safetensors, 27 Go float32)
3. Affiche les instructions de conversion OVH

### ⚠️ Problèmes rencontrés
| Problème | Cause | Fix |
|---|---|---|
| `ValueError: offload_dir needed` | RTX 5060 (8 Go) insuffisant pour Mistral 7B float16 — dispatch sur CPU nécessaire | Ajout `offload_folder=str(offload_dir)` dans `from_pretrained` + `PeftModel.from_pretrained` |
| Export terminé en 22s sans `models/merged/` | Lignes `merge_and_unload()` + `save_pretrained()` manquantes dans le script (bug copier-coller) | Restaurer le corps complet de `merge_lora()` |
| `load_dotenv` not defined | Import manquant dans `export_gguf.py` | Ajouter `from dotenv import load_dotenv` |

---

## Étape 3 — Conversion GGUF f16 (local) + Transfert + Quantisation OVH

### ⚠️ Important : architecture de conversion
`convert_hf_to_gguf.py` est disponible en local dans `realisations/sg/sg-assurances/llama.cpp/`.
Les binaires compilés (`llama-quantize`, `llama-cli`) sont OVH uniquement (`~/llama-bin/llama-b9682/`).
La conversion doit donc se faire en **deux temps** : f16 en local, quantisation sur OVH.

### Étape 3a — Conversion f16 en local
```
cd "realisations\sg\sg-assurances\llama.cpp"
python convert_hf_to_gguf.py "..\..\..\sanofi\training\models\merged" ^
  --outfile "..\..\..\sanofi\training\models\mistral7b-drug-f16.gguf" ^
  --outtype f16
```
Résultat : `training/models/mistral7b-drug-f16.gguf` (~14 Go)

### Étape 3b — Vérifier espace OVH avant transfert
```
ssh ubuntu@51.68.130.23
df -h
```
Il faut **au minimum 20 Go libres** pour recevoir le f16 (14 Go) + sortie Q4_K_M (4 Go) en simultané.

Si insuffisant :
```
docker image prune -f   # supprime images dangling
```

### Étape 3c — Créer les dossiers sur OVH (si première fois)
```
mkdir -p /home/ubuntu/ml-project/realisations/sanofi/ml/models
```
Note : `training/models/` sur OVH n'est PAS nécessaire — le f16 va directement dans `ml/models/`.

### Étape 3d — Transférer le f16 vers OVH
```
scp "C:\Users\iandr\...\training\models\mistral7b-drug-f16.gguf" ubuntu@51.68.130.23:/home/ubuntu/ml-project/realisations/sanofi/ml/models/
```

### Étape 3e — Quantisation Q4_K_M sur OVH
```
cd /home/ubuntu/llama-bin/llama-b9682
./llama-quantize \
  /home/ubuntu/ml-project/realisations/sanofi/ml/models/mistral7b-drug-f16.gguf \
  /home/ubuntu/ml-project/realisations/sanofi/ml/models/mistral7b-drug.gguf \
  Q4_K_M
```
Résultat : `ml/models/mistral7b-drug.gguf` (~4.1 Go)

### Étape 3f — Valider + nettoyer
```
# Tester le modèle (contexte réduit pour éviter OOM)
./llama-cli -m /home/ubuntu/ml-project/realisations/sanofi/ml/models/mistral7b-drug.gguf \
  -p '[INST] What is IL4R? [/INST]' -n 60 -c 512

# Supprimer le f16 intermédiaire (libère 14 Go)
rm /home/ubuntu/ml-project/realisations/sanofi/ml/models/mistral7b-drug-f16.gguf
```

### ⚠️ Problèmes rencontrés
| Problème | Cause | Fix |
|---|---|---|
| `llama-cli` killed au premier lancement | Contexte `-c 4096` par défaut → OOM sur 7.6 Gi RAM | Ajouter `-c 512` pour le test uniquement |
| Espace disque insuffisant | Deux llama-servers à `-c 2048` + images Docker dangling | `docker image prune -f` (libère ~15 Go de dangling) |
| `convert_hf_to_gguf.py` introuvable sur OVH | Seuls les binaires compilés sont sur OVH, pas les scripts Python | Faire la conversion f16 en local via `sg/llama.cpp/` |

---

## Étape 4 — Configurer llama-server Sanofi (OVH, une seule fois)

### Créer le service systemd
```
sudo nano /etc/systemd/system/llama-server-sanofi.service
```

Contenu :
```ini
[Unit]
Description=llama-server Mistral 7B Sanofi Drug Discovery
After=network.target

[Service]
Type=simple
User=ubuntu
ExecStart=/home/ubuntu/llama-bin/llama-b9682/llama-server -m /home/ubuntu/ml-project/realisations/sanofi/ml/models/mistral7b-drug.gguf --port 8006 --host 0.0.0.0 -c 2048 --threads 4
Restart=on-failure
RestartSec=10
StandardOutput=append:/home/ubuntu/llama-server-sanofi.log
StandardError=append:/home/ubuntu/llama-server-sanofi.log

[Install]
WantedBy=multi-user.target
```

### Activer et démarrer
```
sudo systemctl daemon-reload
sudo systemctl enable llama-server-sanofi
sudo systemctl start llama-server-sanofi
sudo systemctl status llama-server-sanofi
```

### Vérifier
```
ss -tlnp | grep 8006
# Résultat attendu : LISTEN 0 512 0.0.0.0:8006
```

### ⚠️ Problèmes rencontrés
| Problème | Cause | Fix |
|---|---|---|
| OOM avec deux llama-servers à `-c 2048` | Mistral 7B (~4-5 Go) + Qwen SG (~1 Go) + KV cache 2048 dépasse 7.6 Gi | SG à `-c 1024` (suffisant pour ses prompts courts) |
| `400 Bad Request` depuis graph_rag.py | Prompt Graph RAG (~900 tokens) + 300 tokens génération > `-c 512` | Passer à `-c 2048` |
| `500 Internal Server Error` après 109s | OOM pendant génération avec deux serveurs à `-c 2048` | Stopper temporairement Qwen SG ou upgrade VPS 16 Go |

---

## Étape 5 — Configurer le réseau Docker pour llama-server

### Problème de réseau
`graph_rag.py` tourne dans le conteneur Docker `sanofi-ml-network` (réseau bridge custom).
`llama-server` tourne en systemd sur le host OVH.
La gateway de `sanofi-ml-network` est **172.21.0.1** (pas 172.17.0.1 comme pour SG qui n'a pas de réseau custom).

### Vérifier la gateway
```
docker network inspect sanofi-ml-network | grep Gateway
```

### Autoriser l'accès depuis le conteneur
```
sudo iptables -I INPUT -s 172.21.0.0/16 -p tcp --dport 8006 -j ACCEPT
```

### Dans graph_rag.py
```python
LLAMA_SERVER_URL = "http://172.21.0.1:8006/v1/chat/completions"
```

### ⚠️ Problèmes rencontrés
| Problème | Cause | Fix |
|---|---|---|
| `ConnectTimeout` depuis le conteneur | Réseau custom `sanofi-ml-network` gateway ≠ `172.17.0.1` | Vérifier gateway via `docker network inspect` |
| `172.21.0.1` inaccessible malgré `0.0.0.0:8006` | iptables bloque le trafic inter-réseau | `sudo iptables -I INPUT -s 172.21.0.0/16 -p tcp --dport 8006 -j ACCEPT` |

---

## Étape 6 — Ingestion Neo4j (OVH)

### Prérequis
- `results/therapeutic_insight.json` présent sur OVH (généré par therapeutic_insight.py)
- Variables Neo4j dans `.env` OVH

### Variables `.env` OVH requises (à ajouter si absentes)
```
NEO4J_AUTH=neo4j/<password>
NEO4J_USER=neo4j
NEO4J_PASSWORD=<password>
NEO4J_URI=bolt://neo4j:7687
NEO4J_HEALTH_URL=http://neo4j:7474
```

### Commande
```
docker-compose exec ml-service python pipeline_orchestrator.py --skip-therapeutic
```

### Durée
~14 minutes pour 11 clusters, 11 721 targets, 158 261 relations.

### Résultat attendu
```
[neo4j_ingestion] [DONE] Durée totale : 861.5s
[ORCHESTRATOR] neo4j_ingestion terminé en 862.2s ✓
[ORCHESTRATOR] === Pipeline terminé en 14m 22s ===
```

### ⚠️ Problèmes rencontrés
| Problème | Cause | Fix |
|---|---|---|
| `pipeline_orchestrator.py` abort après 60s | `NEO4J_HEALTH_URL = "http://localhost:7474"` hardcodé (pas lu depuis `.env`) | Remplacer par `os.getenv("NEO4J_HEALTH_URL", "http://neo4j:7474")` |
| Neo4j crash en boucle `Invalid value for NEO4J_AUTH: '/'` | Variables `NEO4J_USER`/`NEO4J_PASSWORD` absentes du `.env` OVH | Ajouter les 5 variables Neo4j dans `.env` OVH |
| `docker-compose exec` bloqué sans output | Absence du flag `-T` / `--no-TTY` (non supporté sur cette version) | Lancer directement sans background : `docker-compose exec ml-service python ...` |
| Neo4j vide après rebuild Docker | Premier lancement en prod — volume `neo4j_data` jamais peuplé | Lancer `pipeline_orchestrator.py --skip-therapeutic` une fois après chaque destruction de volume |

---

## Étape 7 — Évaluation win-rate (local)

### Prérequis
- Ollama local avec `gemma3:12b` installé (`ollama list`)
- `models/checkpoints_history.json` présent
- `models/lora/checkpoint-346/` présent

### Commande
```
cd realisations\sanofi\training
python evaluate.py
```

### Durée
~24 minutes (15 questions × 3 générations × GPU local).

### Résultat obtenu
```
Win-rate global : 46.7%  (seuil : 30.0%)
Verdict         : ✅ VALIDÉ
  Victoires : 7/15
  Égalités  : 0/15
  Défaites  : 8/15

Par langue :
  EN : 37.5% (3/8)
  FR : 57.1% (4/7)

Par type de question :
  cluster      : 33.3% (1/3)
  target       : 40.0% (2/5)
  drug         : 66.7% (2/3)
  pathway      : 50.0% (1/2)
  comparative  : 50.0% (1/2)
```

### ⚠️ Problèmes rencontrés
| Problème | Cause | Fix |
|---|---|---|
| `ValueError: Some modules dispatched on CPU` au premier chargement | RTX 5060 (8 Go) insuffisant pour Mistral 7B 4-bit — offload nécessaire | Ajout `offload_folder` dans `from_pretrained` |
| `RuntimeError: Tensor.item() cannot be called on meta tensors` au second chargement (fine-tuné) | `accelerate` laisse des artefacts "meta" dans le process après libération du modèle base | Architecture subprocess : `generate_base.py` + `generate_ft.py` — chaque modèle dans un process Python isolé |
| Évaluation très longue (~120 min) avec 20 questions | 3 générations × 20 questions × temps GPU | Réduction à 15 questions (8 EN + 7 FR) |

---

## Étape 8 — Register Vertex AI (local)

### Prérequis
- `models/eval_results.json` avec `win_rate >= 30.0`
- `gcp_sa_sanofi.json` dans `realisations/sanofi/` (un niveau au-dessus de `training/`)
- Bucket GCS `sanofi-models` créé manuellement
- SA `pipeline-sanofi` avec rôles IAM corrects

### Créer le bucket GCS (une seule fois)
```
gcloud storage buckets create gs://sanofi-models \
  --project=gen-lang-client-0989575872 \
  --location=europe-west9 \
  --uniform-bucket-level-access
```

### Donner les droits à la SA
```
gcloud storage buckets add-iam-policy-binding gs://sanofi-models \
  --member="serviceAccount:pipeline-sanofi@gen-lang-client-0989575872.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding gen-lang-client-0989575872 \
  --member="serviceAccount:pipeline-sanofi@gen-lang-client-0989575872.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

### Commande
```
cd realisations\sanofi\training
python register_model.py
```

### Ce qui est uploadé
**Adaptateurs LoRA seulement** (`models/lora/checkpoint-346/`, ~500 Mo) — pas le modèle mergé (27 Go). Sélection automatique via `checkpoints_history.json`.

### ⚠️ Problèmes rencontrés
| Problème | Cause | Fix |
|---|---|---|
| `403 storage.buckets.create denied` | Bucket inexistant + SA sans droits de création | Créer le bucket manuellement via `gcloud`, donner `storage.objectAdmin` à la SA |
| `403 aiplatform.models.list denied` | SA sans rôle Vertex AI | `gcloud projects add-iam-policy-binding ... --role="roles/aiplatform.user"` |
| `400 Model directory expected to contain model.mar` | Container HuggingFace standard attend un `.mar` TorchServe | Utiliser container `huggingface-cpu.2-3` sans `predict_route`/`health_route` |
| `client.get_bucket()` → 403 même si bucket existe | SA a `objectAdmin` mais pas `buckets.get` | Remplacer `client.get_bucket()` par `client.bucket()` (pas d'appel API) |
| `SA_KEY_PATH` pointe vers `training/` au lieu de `sanofi/` | Chemin hardcodé dans le script | `SA_KEY_PATH = TRAINING_DIR.parent / "gcp_sa_sanofi.json"` |

---

## Étape 9 — Déploiement Graph RAG (OVH + Scaleway)

### 9a — Rebuild Docker OVH
```
cd /home/ubuntu/ml-project/realisations/sanofi/ml
docker-compose down && docker-compose build --no-cache && docker-compose up -d
```

### 9b — Vérifier `.dockerignore`
`realisations/sanofi/ml/.dockerignore` doit contenir :
```
models/
__pycache__/
*.pyc
.env
```
Sans ce fichier, Docker envoie 4+ Go au daemon (dont `mistral7b-drug.gguf`).

### 9c — Tester l'endpoint Graph RAG
```
curl -X POST http://51.68.130.23:8001/ml/graph-rag \
  -H "Content-Type: application/json" \
  -d '{"cluster_id": 0, "question": "Quelles sont les cibles les plus prometteuses ?"}'
```

Temps de réponse attendu : **~125-140 secondes** (Neo4j ~5s + Cypher ~2s + Mistral 7B ~120s).

### 9d — Paramètres graph_rag.py (valeurs finales)
```python
LLM_AVAILABLE       = True
LLAMA_SERVER_URL    = "http://172.21.0.1:8006/v1/chat/completions"
LLAMA_MAX_TOKENS    = 200
LLAMA_TIMEOUT       = 180.0
# Cypher : LIMIT 3 par signal (au lieu de 5)
# Contexte : médicaments[:2], maladies[:1], pathways[:2], target_class[:2]
```

### 9e — Commit + push + merge
```
git add .
git commit -m "feat(sanofi): Release 2 Bloc B — Graph RAG LLM activé, win-rate 46.7%, Vertex AI enregistré"
git push origin feature/therapeutic-insight

git checkout infra-scaleway-v1.1
git merge feature/therapeutic-insight
git push origin infra-scaleway-v1.1
```
→ CI/CD déclenche automatiquement le redeploy backend + frontend Scaleway.

### ⚠️ Problèmes rencontrés
| Problème | Cause | Fix |
|---|---|---|
| `504 ML service timeout` depuis frontend | Timeout backend Scaleway à 60s < 140s de réponse réelle | `httpx.AsyncClient(timeout=180.0)` dans `ml.py` |
| `400 Bad Request` llama-server | Prompt Graph RAG (~900 tokens) + 300 génération > `-c 512` | `-c 2048` dans le service systemd |
| `LLM not available` malgré code correct | Image Docker contient l'ancienne version — rebuild sans `--no-cache` insuffisant parfois | `docker-compose down && docker-compose build --no-cache && docker-compose up -d` |
| `Sending build context 4 Go` | `mistral7b-drug.gguf` inclus dans le build context | Ajouter `models/` dans `.dockerignore` |
| `timed out` après correction 400 | `LLAMA_TIMEOUT = 120s` < 142s de génération réelle | `LLAMA_TIMEOUT = 180.0` dans `graph_rag.py` |
| `500 Internal Server Error` après 109s | OOM — deux llama-servers à `-c 2048` sur 7.6 Gi | Stopper Qwen SG pendant tests Sanofi intensifs |

---

## État infra OVH final

### Services systemd actifs
| Service | Modèle | Port | Contexte | RAM estimée |
|---|---|---|---|---|
| `llama-server` | Qwen SG Q4_K_M (934 Mo) | 8005 | -c 1024 | ~1 Go |
| `llama-server-sanofi` | Mistral 7B Q4_K_M (4.1 Go) | 8006 | -c 2048 | ~4-5 Go |

### RAM disponible avec les deux actifs
~1.7 Gi disponibles — suffisant pour les requêtes normales (Neo4j + conteneurs), mais tendu pour des tests intensifs simultanés SG + Sanofi. Upgrade VPS 16 Go recommandé ou start/stop on-demand à implémenter.

### Réseau Docker
- `sanofi-ml-network` — gateway `172.21.0.1`
- `llama-server-sanofi` accessible depuis le conteneur via `172.21.0.1:8006` (règle iptables requise)

---

## Fichiers créés / modifiés cette release

### Nouveaux fichiers
```
realisations/sanofi/training/
    ├── generate_base.py          ← subprocess évaluation modèle base
    ├── generate_ft.py            ← subprocess évaluation modèle fine-tuné
    └── models/
        ├── checkpoints_history.json  ← traçabilité checkpoints (versionné Git)
        └── vertex_model_id.txt       ← resource name Vertex AI

realisations/sanofi/ml/
    └── .dockerignore             ← exclut models/ du build context
```

### Fichiers modifiés
```
realisations/sanofi/training/
    ├── finetune.py       ← _save_checkpoints_history() ajoutée
    ├── export_gguf.py    ← select_best_checkpoint() + offload_folder + client.bucket()
    ├── evaluate.py       ← refonte complète (HuggingFace 4-bit + subprocess + 15 questions)
    └── register_model.py ← SA_KEY_PATH.parent + client.bucket() + LoRA au lieu de merged

realisations/sanofi/ml/
    ├── graph_rag.py      ← LLM_AVAILABLE=True + LLAMA_SERVER_URL 172.21.0.1:8006 + LIMIT 3
    └── pipeline_orchestrator.py ← NEO4J_HEALTH_URL via os.getenv()

backend/routers/sanofi/
    └── ml.py             ← timeout 180s sur post_graph_rag()

frontend/components/sanofi/ml/
    └── ClusteringView.tsx ← PROFILE_QUESTIONS + progress bar + chronomètre
```

---

## Backlog post-release

| Item | Priorité | Contexte |
|---|---|---|
| Start/stop on-demand llama-server-sanofi | Haute | RAM OVH tendue avec deux LLM actifs simultanément |
| Upgrade VPS OVH 16 Go | Haute | Résoudre définitivement le problème RAM sans jongler |
| Streaming token par token Graph RAG | Moyenne | UX : éviter 140s de spinner silencieux |
| `convert_hf_to_gguf.py` dans `sanofi/training/` | Basse | Éviter de dépendre du clone llama.cpp SG |
| Règle iptables persistante au reboot OVH | Basse | `sudo iptables-save` + règle dans `/etc/iptables/rules.v4` |