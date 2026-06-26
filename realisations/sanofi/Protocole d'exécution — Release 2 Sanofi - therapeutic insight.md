# Protocole d'exécution — Release 2 Sanofi
## Therapeutic Insight — Exécution manuelle

---

## Prérequis

- Être sur la branche `feature/therapeutic-insight`
- OVH accessible : `ssh ubuntu@51.68.130.23`
- Backend local : `cd backend && docker-compose up`
- Frontend local : `cd frontend && npm run dev`

---

## Étape 1 — Régénérer le clustering (si nouvelles données)

> À faire uniquement si de nouveaux essais cliniques ont été ingérés dans BigQuery depuis la dernière exécution.

**Sur OVH :**
```
ssh ubuntu@51.68.130.23
cd /home/ubuntu/ml-project/realisations/sanofi/ml
docker-compose run --rm ml-service python clustering.py
```

Vérifier :
```
cat results/clustering.json | python3 -c "import json,sys; d=json.load(sys.stdin); print('Trials:', d['total_trials'], '| Clusters:', d['n_clusters'])"
```

Résultat attendu : `Trials: 441 | Clusters: 11`

---

## Étape 2 — Régénérer therapeutic_insight.json

> À faire si les données OpenTargets doivent être rafraîchies ou si le script a été modifié.

**Sur OVH — lancement en arrière-plan :**
```
ssh ubuntu@51.68.130.23
cd /home/ubuntu/ml-project/realisations/sanofi/ml
nohup docker-compose run --rm -e PYTHONUNBUFFERED=1 ml-service python therapeutic_insight.py > /tmp/ti.log 2>&1 &
```

**Suivre la progression :**
```
tail -f /tmp/ti.log
```

**Vérifier que le process tourne :**
```
ps aux | grep therapeutic
```

**Durée estimée :** 45-90 minutes selon le volume de conditions et la latence OpenTargets.

**Vérifier la fin :**
```
cat /tmp/ti.log | grep "généré"
```

Résultat attendu :
```
✓ therapeutic_insight.json généré — temps total : Xm Xs
```

---

## Étape 3 — Récupérer le JSON en local

> Après la fin du script sur OVH, rapatrier le fichier en local.

**Depuis ton poste local (Cmder) :**
```
scp ubuntu@51.68.130.23:/home/ubuntu/ml-project/realisations/sanofi/ml/results/therapeutic_insight.json realisations/sanofi/ml/results/therapeutic_insight.json
```

---

## Étape 4 — Valider le JSON

**Vérifier la route ML OVH :**
```
curl http://51.68.130.23:8001/ml/therapeutic-insight
```

Résultat attendu : JSON avec `n_clusters: 11`, `clusters[]` avec `targets[]` contenant `approved_name`, `pathways`, `drugs`, `interactions`, `tractability`.

**Vérifier la route backend local :**
```
curl http://localhost:8000/sanofi/ml/therapeutic-insight
```

**Vérifier le frontend local :**
Ouvrir `http://localhost:3000/realisations/sanofi` → ML Insights → Clustering → scatter plot visible + signaux au clic.

---

## Étape 5 — Rebuilder le ML service OVH

> À faire si `main.py` ou `therapeutic_insight.py` ont été modifiés.

```
ssh ubuntu@51.68.130.23
cd /home/ubuntu/ml-project/realisations/sanofi/ml
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

Vérifier :
```
docker-compose logs
```

Résultat attendu : `✅ ML results loaded into cache` avec `therapeutic_insight` dans la liste.

---

## Étape 6 — Commit et push

> Une fois tout validé en local.

```
git add realisations/sanofi/ml/therapeutic_insight.py
git add realisations/sanofi/ml/main.py
git add realisations/sanofi/ml/clustering.py
git add backend/routers/sanofi/router.py
git add backend/routers/sanofi/ml.py
git add frontend/lib/sanofiApi.ts
git add frontend/components/sanofi/ml/MlView.tsx
git add frontend/components/sanofi/ml/ClusteringView.tsx
git commit -m "feat(sanofi): Release 2 - Therapeutic Insight"
git push origin feature/therapeutic-insight
```

> Ne pas committer `results/therapeutic_insight.json` — fichier trop lourd, transféré via scp.

---

## Étape 7 — Merge vers infra-scaleway-v1.1

```
git checkout infra-scaleway-v1.1
git merge feature/therapeutic-insight
git push origin infra-scaleway-v1.1
```

Le CI/CD GitHub Actions déclenche automatiquement le redeploy backend + frontend Scaleway.

---

## Étape 8 — Vérifier en prod Scaleway

**Backend :**
```
curl https://<backend-scaleway-url>/sanofi/ml/therapeutic-insight
```

**Frontend :**
Ouvrir `https://<frontend-scaleway-url>/realisations/sanofi` → ML Insights → Clustering.

---

## Paramètres configurables du script

Modifiables en tête de `realisations/sanofi/ml/therapeutic_insight.py` :

| Paramètre | Valeur actuelle | Rôle |
|---|---|---|
| `DISEASES_PER_CONDITION` | 5 | Diseases OpenTargets retournées par condition |
| `SCORE_THRESHOLD_DISEASE` | 0 | Seuil score disease (0 = tout garder) |
| `TARGETS_PER_DISEASE` | 25 | Cibles biologiques par disease |
| `REQUEST_DELAY_SEC` | 0.05 | Délai entre requêtes OpenTargets |

---

## Commandes utiles OVH

| Action | Commande |
|---|---|
| Voir les logs du script | `cat /tmp/ti.log` |
| Suivre en temps réel | `tail -f /tmp/ti.log` |
| Vérifier process actif | `ps aux \| grep therapeutic` |
| Tuer le process (si besoin) | `sudo kill <PID>` |
| Status container ML | `docker-compose logs` |
| Vérifier JSON présent | `ls -la results/` |
| Tester route ML | `curl http://51.68.130.23:8001/ml/therapeutic-insight` |
| Tester route orchestrateur | `curl -X POST http://51.68.130.23:8080/wake -H "Content-Type: application/json" -d "{\"service_key\": \"sanofi-ml\"}"` |