# Sanofi — Procédure de mise à jour données + Réentraînement (optionnel)

> Dernière révision : session du 09-10 juillet 2026 — Bloc A/B séparés, option exécution locale + scp

---

## Prérequis

- Accès SSH OVH : `ssh ubuntu@51.68.130.23`
- Tous les fichiers `realisations/` sont déjà présents sur OVH (pipeline/, ml/, training/)
- Secrets déjà présents sur OVH : `.env` racine + `.env` ml/ + `gcp_sa_sanofi.json`
- Vérifier l'orchestrateur on-demand actif avant de commencer :
  ```bash
  curl http://localhost:8080/health
  ```
  Si down :
  ```bash
  docker start ovh-orchestrator
  ```

---

## ⚠️ Règles apprises pendant le debug — à respecter strictement

| Règle | Pourquoi |
|---|---|
| Toujours utiliser `docker-compose run --rm`, jamais `exec`, pour les scripts one-shot | `exec` échoue silencieusement si le container cible est arrêté (Exit 0) |
| Toujours ajouter `-e PYTHONUNBUFFERED=1` sur les runs longs | Sans ça, les logs de `therapeutic_insight.py` restent invisibles pendant toute la durée du script |
| Ne jamais juger un script "bloqué" sur la seule absence de logs | Vérifier `docker stats <container_id>` — CPU actif = ça travaille, même en silence |
| Réveiller les services via `/wake`, pas `docker-compose up -d` manuellement | Le timer d'auto-sleep de l'orchestrateur ne s'arme QUE via `/wake` — un démarrage manuel reste up indéfiniment |
| La durée de `therapeutic_insight.py` scale avec le volume de cibles biologiques | Un cluster à +1200 cibles peut dépasser largement l'estimation de 45-90 min |
| `therapeutic_insight.py` et `pipeline_orchestrator.py` sont TOUJOURS séparés | Jamais un seul appel combiné — voir Étape 4a/4b |

---

# PARTIE 1 — Mise à jour des données en prod (Bloc A + Bloc B)

À faire à chaque nouvel essai clinique Sanofi ingéré. **Pas de réentraînement du LLM dans cette partie.**

Deux façons d'exécuter cette partie : **tout sur OVH** (recommandé, plus simple), ou **calcul en local + transfert scp** (utile si tu veux suivre les logs plus confortablement sur ta machine, ou si OVH est chargé).

## Étape 0 — Réveiller ml-service proprement
```bash
curl -X POST http://localhost:8080/wake/sanofi-ml
```
(vérifier la clé exacte du registry via `curl http://localhost:8080/status` si différente — non confirmé à ce jour)

## Étape 1 — ETL (collecte de base)
```bash
ssh ubuntu@51.68.130.23
cd /home/ubuntu/ml-project/realisations/sanofi/
docker-compose run --rm pipeline python pipeline/orchestrator.py
```
→ ClinicalTrials + PubMed + Google News + Press Releases → BigQuery + ChromaDB

Optionnel, 90 min après (enrichissement Google News) :
```bash
docker-compose run --rm pipeline python pipeline/enrich_orchestrator.py
```

## Étape 2 — Clustering

### Option A — Sur OVH
```bash
cd ../ml
docker-compose run --rm ml-service python clustering.py
```

### Option B — En local
```cmd
cd realisations\sanofi\ml
docker-compose run --rm ml-service python clustering.py
```
Puis transfert vers OVH :
```bash
scp realisations/sanofi/ml/results/clustering.json ubuntu@51.68.130.23:/home/ubuntu/ml-project/realisations/sanofi/ml/results/
```

Vérifier (sur OVH ou en local selon où tu l'as généré) :
```bash
cat results/clustering.json | python3 -c "import json,sys; d=json.load(sys.stdin); print('Trials:', d['total_trials'], '| Clusters:', d['n_clusters'])"
```
Attendu : `Trials: 441 | Clusters: 11` (le nombre de trials augmentera avec les nouveaux essais)

## Étape 3 — Forecasting + Topic Modeling (indépendants)

### Option A — Sur OVH
```bash
docker-compose run --rm ml-service python forecasting.py
docker-compose run --rm ml-service python topic_modeling.py
```

### Option B — En local + scp
```cmd
docker-compose run --rm ml-service python forecasting.py
docker-compose run --rm ml-service python topic_modeling.py
```
```bash
scp realisations/sanofi/ml/results/forecasting.json ubuntu@51.68.130.23:/home/ubuntu/ml-project/realisations/sanofi/ml/results/
scp realisations/sanofi/ml/results/topic_modeling.json ubuntu@51.68.130.23:/home/ubuntu/ml-project/realisations/sanofi/ml/results/
```

## Étape 4a — Bloc A : therapeutic_insight.py (toujours séparé de 4b)

### Option A — Sur OVH
```bash
nohup docker-compose run --rm -e PYTHONUNBUFFERED=1 ml-service python therapeutic_insight.py > /tmp/ti.log 2>&1 &
tail -f /tmp/ti.log
```

### Option B — En local + scp
```cmd
cd realisations\sanofi\ml
docker-compose run --rm -e PYTHONUNBUFFERED=1 ml-service python therapeutic_insight.py
```
Puis transfert vers OVH une fois terminé :
```bash
scp realisations/sanofi/ml/results/therapeutic_insight.json ubuntu@51.68.130.23:/home/ubuntu/ml-project/realisations/sanofi/ml/results/
```

**Avantage de l'option B** : logs visibles directement dans ton terminal local sans souci de buffering Docker/SSH, pas de risque de coupure si ta connexion SSH tombe.
**Inconvénient** : ta machine locale doit tourner pendant toute la durée du calcul (variable, potentiellement plusieurs heures selon le volume de cibles).

Suivre la progression (si Option A, sur OVH) :
```bash
ps aux | grep therapeutic_insight
docker stats <container_id>   # vérifier CPU actif en complément des logs
```

Vérifier la fin :
```bash
cat /tmp/ti.log | grep "généré"
```
(ou directement dans le terminal si Option B)

## Étape 4b — Bloc B : Neo4j (avec --skip-therapeutic, toujours sur OVH)
```bash
ssh ubuntu@51.68.130.23
cd /home/ubuntu/ml-project/realisations/sanofi/ml
docker-compose run --rm ml-service python pipeline_orchestrator.py --skip-therapeutic
```
- Le flag est **obligatoire** ici : le JSON existe déjà (généré à l'étape 4a, sur OVH ou en local+scp), pas besoin de le régénérer
- Durée : ~14 minutes
- Neo4j étant sur OVH, cette étape se fait toujours côté serveur, même si 4a a été fait en local

## Étape 5 — Redémarrer ml-service (recharge cache JSON)
```bash
docker-compose down
docker-compose up -d ml-service
curl http://localhost:8001/health
```
Attendu :
```json
{"status": "ok", "cached": ["clustering", "forecasting", "topic_modeling", "therapeutic_insight"]}
```

Vérifier aussi `llama-server-sanofi` (port 8006, nécessaire pour le Graph RAG) :
```bash
sudo systemctl status llama-server-sanofi
```

## Étape 6 — Vérifications endpoints
```bash
curl http://51.68.130.23:8001/ml/clustering
curl http://51.68.130.23:8001/ml/forecasting
curl http://51.68.130.23:8001/ml/topic-modeling
curl http://51.68.130.23:8001/ml/therapeutic-insight
curl -X POST http://51.68.130.23:8001/ml/graph-rag \
  -H "Content-Type: application/json" \
  -d '{"cluster_id": 0, "question": "Test"}'
```

## Étape 7 — Laisser l'auto-sleep faire son travail
Rien à faire — si le service a été réveillé via `/wake` (Étape 0), il s'éteindra automatiquement après la période d'inactivité configurée.

---

# PARTIE 2 — Réentraînement du LLM (optionnel, séparé de la mise à jour de données)

> ⚠️ Aucun lien automatique avec la Partie 1. À faire seulement si : nouveau dataset Q&A, win-rate insuffisant, ou changement de modèle de base.

## Étape B1 — Fine-tuning Mistral 7B (local, RTX 5060)
Prérequis : `venv-sanofi` activé, `training/data/dataset_train.jsonl` + `dataset_eval.jsonl` présents (sinon `python prepare_dataset.py` d'abord)
```cmd
cd realisations\sanofi\training
python finetune.py
```
Durée : ~216 min (3h36)
Résultat : `models/lora/checkpoint-346/` (meilleur checkpoint, sélectionné automatiquement via `checkpoints_history.json`)

⚠️ Avant un nouveau run d'évaluation, nettoyer :
```cmd
del models\eval_base_responses.json
del models\eval_ft_responses.json
```

## Étape B2 — Export merge LoRA (local)
```cmd
cd realisations\sanofi\training
python export_gguf.py
```
→ `models/merged/` (~27 Go float32)

## Étape B3a — Conversion GGUF f16 (local)
```cmd
cd "realisations\sg\sg-assurances\llama.cpp"
python convert_hf_to_gguf.py "..\..\..\sanofi\training\models\merged" ^
  --outfile "..\..\..\sanofi\training\models\mistral7b-drug-f16.gguf" ^
  --outtype f16
```

## Étape B3b — Vérifier espace disque OVH avant transfert
```bash
ssh ubuntu@51.68.130.23
df -h
```
Minimum 20 Go libres requis (f16 14 Go + Q4_K_M 4 Go en simultané)

## Étape B3c — Transfert + Quantisation OVH
```bash
scp realisations/sanofi/training/models/mistral7b-drug-f16.gguf ubuntu@51.68.130.23:~/ml-project/realisations/sanofi/ml/models/
ssh ubuntu@51.68.130.23
cd ~/llama-bin/llama-b9682/
./llama-quantize ~/ml-project/realisations/sanofi/ml/models/mistral7b-drug-f16.gguf \
  ~/ml-project/realisations/sanofi/ml/models/mistral7b-drug.gguf Q4_K_M
```

## Étape B4 — Redémarrer llama-server-sanofi
```bash
sudo systemctl restart llama-server-sanofi
sudo systemctl status llama-server-sanofi
```

## Étape B5 — Réingestion Neo4j
```bash
cd ~/ml-project/realisations/sanofi/ml
docker-compose run --rm ml-service python pipeline_orchestrator.py --skip-therapeutic
```
Durée : ~14 min pour 11 clusters / ~11 700 targets / ~158 000 relations

## Étape B6 — Évaluation win-rate (local)
Prérequis : Ollama local avec `gemma3:12b` (`ollama list`)
```cmd
cd realisations\sanofi\training
python evaluate.py
```
Durée : ~24 min
Seuil de validation : win-rate ≥ 30% (référence actuelle : 46.7%)

## Étape B7 — Enregistrement Vertex AI (local)
Prérequis : `models/eval_results.json` avec `win_rate >= 30.0`
```cmd
cd realisations\sanofi\training
python register_model.py
```
→ Upload uniquement les adaptateurs LoRA (~500 Mo), pas le modèle mergé complet

---

## Résumé visuel — Partie 1 (mise à jour données)

```
0. /wake sanofi-ml
1. pipeline/orchestrator.py (ETL, OVH)              → BigQuery + ChromaDB
2. clustering.py (OVH ou local+scp)                  → clustering.json
3. forecasting.py + topic_modeling.py (OVH ou local+scp) → forecasting.json + topic_modeling.json
4a. therapeutic_insight.py (OVH ou local+scp, SÉPARÉ) → therapeutic_insight.json
4b. pipeline_orchestrator.py --skip-therapeutic (OVH, TOUJOURS) → Neo4j réingéré
5. Redémarrer ml-service + vérifier llama-server-sanofi
6. Vérifs endpoints
7. Auto-sleep (rien à faire)
```

## Résumé visuel — Partie 2 (réentraînement, optionnel)

```
B1. finetune.py (local, ~3h36)              → checkpoint-346
B2. export_gguf.py (local)                   → models/merged/ (27 Go)
B3. convert_hf_to_gguf.py (local) + scp + llama-quantize (OVH) → GGUF Q4_K_M (4 Go)
B4. restart llama-server-sanofi
B5. pipeline_orchestrator.py --skip-therapeutic → Neo4j réingéré
B6. evaluate.py (local, ~24 min)              → win-rate
B7. register_model.py (local)                 → Vertex AI + GCS
```