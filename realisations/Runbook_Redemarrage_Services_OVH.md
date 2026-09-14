# Runbook OVH — Redémarrage complet de tous les services

*Procédure de référence pour relancer proprement l'ensemble de l'infra OVH (`51.68.130.23`) après un incident, un reboot du VPS, ou une maintenance. Consolide les leçons de la nuit du 03/09/2026 (collision de tags d'image, bug `docker-compose` `ContainerConfig`, prune ayant supprimé des conteneurs en prod).*

---

## 0. Avant de commencer — état des lieux

```bash
ssh ubuntu@51.68.130.23
free -h
df -h /
docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"
```

Ne lance rien tant que tu n'as pas ces 3 résultats sous les yeux — ça évite de reproduire un rebuild inutile sur un service déjà sain.

---

## 1. Services always-on — vérifier en premier, ne jamais les stopper

```bash
docker ps | grep -E "chromadb|orchestrator"
curl http://localhost:8000/api/v2/heartbeat
curl http://localhost:8080/health
curl http://localhost:8080/status
```

Le `/status` doit lister **tous** les services suivants : `chromadb`, `sanofi-ml`, `savencia-ml`, `sg-ml`, `embedding-service`, `banque-ml`, `gestion-patrimoine-ml`, `neo4j`. Si l'un manque, `registry.yaml` n'est pas à jour ou l'orchestrateur ne l'a pas rechargé — voir §7.

Si `ovh-orchestrator` n'apparaît pas ou est down :
```bash
cd /home/ubuntu/ml-project/ovh
docker-compose up -d
```

---

## 2. Embedding-service — à réveiller en priorité (partagé par 3 MVPs)

```bash
cd /home/ubuntu/ml-project/realisations/sg/sg-assurances/embedding-service
docker-compose up -d
sleep 5
curl http://localhost:8004/health
docker stop embedding-service   # remettre en sommeil une fois vérifié, sauf si tu vas t'en servir tout de suite
```

---

## 3. Chaque MVP ml-service — rebuild complet, une ligne chaînée par service

Format standard : `cd → docker rm -f → docker-compose build → up -d → sleep → curl health → stop`. Le `rm -f` avant `build` contourne systématiquement le bug `ContainerConfig` (§8) — plus besoin de `--force-recreate`, jamais.

Ordre suggéré (du plus simple au plus complexe) : Savencia → SG → Embedding → Banque de France → Gestion Patrimoine → Sanofi (Neo4j en plus, séparé).

```bash
cd /home/ubuntu/ml-project/realisations/sanofi/ml && docker rm -f ml_ml-service_1 && docker-compose build && docker-compose up -d && sleep 5 && curl http://localhost:8001/health && docker stop ml_ml-service_1

cd /home/ubuntu/ml-project/realisations/savencia/ml && docker rm -f ml_savencia-ml-service_1 && docker-compose build && docker-compose up -d && sleep 5 && curl http://localhost:8002/health && docker stop ml_savencia-ml-service_1

cd /home/ubuntu/ml-project/realisations/sg/sg-assurances/ml && docker rm -f sg-ml-service && docker-compose build && docker-compose up -d && sleep 5 && curl http://localhost:8003/health && docker stop sg-ml-service

cd /home/ubuntu/ml-project/realisations/sg/sg-assurances/embedding-service && docker rm -f embedding-service && docker-compose build && docker-compose up -d && sleep 5 && curl http://localhost:8004/health && docker stop embedding-service

cd /home/ubuntu/ml-project/realisations/banque-de-france/ml && docker rm -f banque-ml-service && docker-compose build && docker-compose up -d && sleep 5 && curl http://localhost:8007/health && docker stop banque-ml-service

cd /home/ubuntu/ml-project/realisations/gestion-patrimoine/ml && docker rm -f gestion-patrimoine-ml && docker-compose build && docker-compose up -d && sleep 5 && curl http://localhost:8008/health && docker stop gestion-patrimoine-ml
```

### Cas particulier — Sanofi Neo4j (volume `ml_neo4j_data` à préserver, jamais `docker rm -f` sans vérifier d'abord)

```bash
docker volume ls | grep neo4j   # confirmer que ml_neo4j_data existe avant toute suppression
cd /home/ubuntu/ml-project/realisations/sanofi/ml && docker rm -f sanofi-neo4j && docker-compose up -d neo4j && sleep 15 && curl http://localhost:7474
```

Test complet Graph RAG (ml-service + Neo4j + llama-server-sanofi) une fois les deux up :
```bash
curl -X POST http://localhost:8001/ml/graph-rag \
  -H "Content-Type: application/json" \
  -d '{"cluster_id": 0, "question": "Test"}'
# Vérifier targets_count > 0 avant de considérer Neo4j intact
docker stop ml_ml-service_1 sanofi-neo4j
```

⚠️ **Après tout rebuild avec `docker rm -f` + recréation, vérifie systématiquement le nom final du conteneur** (§9) — il arrive qu'il ressorte préfixé (`<id>_<nom>`) plutôt que sous son nom propre, ce qui cassera sa reconnaissance par l'orchestrateur tant qu'il n'est pas renommé.

---

## 4. Les `llama-server` (systemd) — PAS de wake-on-demand, démarrage 100% manuel

⚠️ Contrairement aux conteneurs Docker ci-dessus, ces services ne se réveillent jamais tout seuls. Si un MVP a besoin de génération LLM et que son `llama-server` est arrêté, la requête échouera avec `[Errno 111] Connection refused` (502 côté `ml-service`).

**Démarrer uniquement ceux dont tu as besoin** (attention à la RAM cumulée — voir §5) :

```bash
# SG (Qwen fine-tuné QLoRA, port 8005)
sudo systemctl start llama-server
curl http://localhost:8005/health

# Sanofi (Mistral 7B fine-tuné, port 8006) — LE PLUS LOURD (~45% RAM)
sudo systemctl start llama-server-sanofi
curl http://localhost:8006/health

# Gestion Patrimoine (Qwen2.5-3B base, port 8009)
sudo systemctl start llama-server-gestion-patrimoine
curl http://localhost:8009/health
```

**Pour les arrêter après usage** (recommandé si tu ne t'en sers pas activement, vu la pression RAM) :
```bash
sudo systemctl stop llama-server
sudo systemctl stop llama-server-sanofi
sudo systemctl stop llama-server-gestion-patrimoine
```

Vérifier l'état de tous en une fois :
```bash
systemctl is-active llama-server llama-server-sanofi llama-server-gestion-patrimoine
```

---

## 5. Vérification RAM — ne jamais dépasser la marge de sécurité

```bash
free -h
ps aux --sort=-%mem | head -10
```

**Repères mesurés dans la nuit du 03/09** (VPS 7,6 Gi total) :
| Service | % RAM |
|---|---|
| Sanofi Mistral 7B | ~45% |
| Qwen 3B (Gestion Patrimoine) | ~22% |
| Qwen SG fine-tuné | ~10% |

**Règle empirique** : ne jamais avoir plus de 2 `llama-server` actifs simultanément sur ce VPS sans upgrade — 3 actifs en même temps a déjà causé RAM < 100 Mi disponible et des `unhealthy`/`502` en cascade.

---

## 6. Vérification finale — tous les `/health` en une passe

```bash
for port in 8000 8001 8002 8003 8004 8005 8006 8007 8008 8009 8080; do
  echo -n "Port $port: "
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost:$port/health 2>/dev/null || echo "unreachable"
done
```

---

## 7. Si un service n'apparaît pas dans `/status` de l'orchestrateur

```bash
grep -A8 "<nom-service>:" /home/ubuntu/ml-project/ovh/orchestrator/registry.yaml
docker exec ovh-orchestrator cat /app/registry.yaml | grep -A8 "<nom-service>:"
```
Si les deux diffèrent ou si le second est vide :
```bash
docker restart ovh-orchestrator
curl http://localhost:8080/status
```

---

## 7bis. Si un wake interne échoue avec `[Errno 111] Connection refused` ou `timed out` (règle `ufw` manquante)

Incident réel du 03-14/09 : `sanofi-neo4j` timeoutait systématiquement au wake (`graph_rag.py` → `_wake_neo4j()`), malgré un `OVH_ORCHESTRATOR_URL` correctement configuré. Cause : **aucune règle `ufw` n'autorisait le réseau `sanofi-ml-network` (`172.21.0.0/16`) à atteindre le port 8080** — restée invisible pendant des mois parce que Neo4j tournait jusque-là en continu (`restart: unless-stopped`), donc jamais réellement testée en conditions de sommeil/réveil réel.

**Vérifier la règle pour un réseau donné :**
```bash
docker network inspect <nom-du-network> | grep Gateway
sudo ufw status numbered | grep 8080
```

**Ajouter si absente :**
```bash
sudo ufw allow from <gateway>/16 to any port 8080 proto tcp
```

**Règles confirmées nécessaires (au 14/09)** :
| Réseau | Gateway | Règle 8080 |
|---|---|---|
| `gestion-patrimoine-ml-network` | 172.25.0.1 | ✅ présente depuis le déploiement initial |
| `sanofi-ml-network` | 172.21.0.1 | ✅ ajoutée le 14/09 (bug corrigé) |
| Savencia / SG / Banque de France | — | confirmées fonctionnelles, pas de wake interne équivalent à `graph_rag.py` testé nécessitant cette vérification |

Si un futur MVP ajoute un service annexe avec son propre mécanisme de wake interne (comme `graph_rag.py` pour Neo4j), penser à vérifier cette règle **avant** de chercher un bug applicatif — c'est un piège qui coûte cher à diagnostiquer (plusieurs heures cette nuit) pour un fix d'une ligne.

---

## 8. Si `docker-compose up`/`--force-recreate` échoue avec `KeyError: 'ContainerConfig'`

Bug connu `docker-compose` 1.29.2 vs moteur Docker récent, sur **toute recréation** de conteneur existant.

```bash
docker ps -a | grep <mvp>          # trouver l'ID/nom exact du conteneur concerné
docker rm -f <id_ou_nom_exact>
docker-compose up -d               # simple up après suppression, pas de --force-recreate nécessaire
```

⚠️ **Ne jamais faire ça sur `sanofi-neo4j` sans vérifier d'abord que le volume `ml_neo4j_data` existe** (`docker volume ls | grep neo4j`) — le conteneur est jetable, les données non.

---

## 9. Si un conteneur recréé apparaît avec un préfixe bizarre (`<id>_<nom>`)

Arrive après un changement de `COMPOSE_PROJECT_NAME` ou de nom de service sur un conteneur déjà existant sous l'ancien nom.

```bash
docker ps -a   # repérer le nom exact avec préfixe
docker rename <id>_<nom_attendu> <nom_attendu>
```

Toujours vérifier après renommage que ça correspond exactement à `container_name` dans `registry.yaml` (§7), sinon l'orchestrateur ne le retrouvera plus.

---

## 10. Ce qu'il ne faut PLUS JAMAIS faire sans vérification préalable

- ❌ `docker container prune` / `docker system prune -a` sans avoir d'abord vérifié `docker ps -a` sur **chaque** MVP — un conteneur `Exited` normal (service endormi wake-on-demand) sera supprimé aveuglément, y compris ceux en prod
- ❌ `docker-compose --force-recreate` sans connaître le bug `ContainerConfig` — toujours préférer `docker rm -f` + `up` simple
- ❌ Modifier un `docker-compose.yml`/`registry.yaml` uniquement sur OVH sans le committer côté Windows — le prochain `git pull` écrasera ou entrera en conflit

---

## 11bis. Repartir de zéro sur tous les `ml-service`

Le format en une ligne de §3 (`rm -f && build && up -d && curl health && stop`) *est* déjà la procédure "repartir de zéro" — il supprime le conteneur avant de le reconstruire, donc aucune étape supplémentaire n'est nécessaire. Relance simplement le bloc complet de §3 dans l'ordre.

---

## 11. Rappel — nommage des projets Docker Compose (fix appliqué le 03/09)

Chaque `ml/.env` (ou `.env` racine du MVP pour gestion-patrimoine) contient désormais :
```env
COMPOSE_PROJECT_NAME=<mvp>-ml
```
Et chaque `docker-compose.yml` déclare un `image:` explicite et unique. Ces deux fixes évitent la collision de tags d'image entre MVPs qui partagent un dossier `ml/` et un service `ml-service` — **ne jamais retirer ces lignes**.
