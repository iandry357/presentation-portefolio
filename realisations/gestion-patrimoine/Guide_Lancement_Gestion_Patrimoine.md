# Guide de lancement — MVP "gestion-patrimoine"

*Procédures opérationnelles : lancement local, gestion OVH, merge en production.*

---

## 1. Lancer le backend en local

```bash
cd backend
```

Vérifier `.env` local (compléter si absent) :
```env
MISTRAL_API_KEY=<clé>
GEMINI_API_KEY=<clé>
OVH_ML_HOST=51.68.130.23
OVH_ORCHESTRATOR_PORT=8080
DATABASE_URL=<url_postgres_scaleway>
```

```bash
docker-compose up -d --build
docker-compose logs -f
curl http://localhost:8000/health
```

---

## 2. Lancer le frontend en local

`frontend/.env.local` :
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

```bash
cd frontend
npm install
npm run dev
```

Ouvrir `http://localhost:3000/realisations/gestion-patrimoine`.

---

## 3. Tests directs (sans UI) — isoler les problèmes

```bash
curl -X POST http://localhost:8000/gestion-patrimoine/profil \
  -H "Content-Type: application/json" \
  -d '{"thematique": "ifi"}'
```

```bash
curl -X POST http://localhost:8000/gestion-patrimoine/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "<session_id_retourné>"}'
```

---

## 4. Vérifier l'état de l'infra OVH avant tout test

```bash
ssh ubuntu@51.68.130.23
free -h
systemctl is-active llama-server llama-server-sanofi llama-server-gestion-patrimoine
```

**Si la RAM est tendue** (moins de ~1 Go disponible), libérer de la place :
```bash
sudo systemctl stop llama-server           # SG, si pas nécessaire pour ce test
sudo systemctl stop llama-server-sanofi    # Sanofi, si pas nécessaire pour ce test
```
Puis les redémarrer une fois le test terminé :
```bash
sudo systemctl start llama-server
sudo systemctl start llama-server-sanofi
```

---

## 5. Réveiller `embedding-service` manuellement si besoin

Si un appel `/chat` timeout sur `embedding-service` (déjà observé une fois en session, cause non totalement élucidée) :
```bash
curl -X POST http://localhost:8080/wake/embedding-service
sleep 5
curl http://localhost:8004/health
```

---

## 6. Rebuild / redémarrer `ml-service` sur OVH

**Toujours isoler le nom de projet Docker Compose** — plusieurs MVPs ont un dossier `ml/` au même nom, source de confusion (`ml_ml-service_1` peut désigner Sanofi par erreur) :

```bash
cd /home/ubuntu/ml-project/realisations/gestion-patrimoine/ml
docker-compose -p gestion-patrimoine-ml up -d --build
docker-compose -p gestion-patrimoine-ml logs -f
```

**Si erreur `KeyError: 'ContainerConfig'`** (bug connu `docker-compose` 1.29.2 vs moteur Docker récent, déjà documenté dans le README principal) :
```bash
docker rm -f gestion-patrimoine-ml
DOCKER_BUILDKIT=0 docker-compose -p gestion-patrimoine-ml up -d --build
```

---

## 7. Test direct sur `ml-service` (sans backend, sans merge)

```bash
curl http://localhost:8009/health
curl http://localhost:8008/health

curl -X POST http://localhost:8008/chat \
  -H "Content-Type: application/json" \
  -d '{"thematique": "ifi", "profil": {"thematique": "ifi", "age": 45, "situation_familiale": "marié", "patrimoine_global": 2500000, "objectif": "réduire l'\''IFI", "details": {"valeur_patrimoine_immobilier_net": 1800000}}}'
```

---

## 8. Vérifier le pilotage orchestrateur

```bash
sudo systemctl restart ovh-orchestrator
curl -X POST http://localhost:8080/wake/gestion-patrimoine-ml
curl http://localhost:8080/status
```

---

## 9. Merger et déployer en production (quand décidé)

```bash
# Windows / Cmder
cd "C:\Users\iandr\Documents\EXP\exp 2.0\projet cv\presentation-portefolio"
git checkout feature/gestion-patrimoine-mvp
git add .
git commit -m "feat(gestion-patrimoine): agents, ml-service, migration, backend, frontend, orchestrateur"

git checkout infra-scaleway-v1.1
git merge feature/gestion-patrimoine-mvp
git push origin infra-scaleway-v1.1
```

Ce push déclenche automatiquement le redeploy backend + frontend Scaleway (CI/CD GitHub Actions).

**Sur OVH — pull manuel (pas de CI/CD côté OVH)** :
```bash
ssh ubuntu@51.68.130.23
cd /home/ubuntu/ml-project
git sparse-checkout list   # vérifier que realisations/gestion-patrimoine y figure
git checkout infra-scaleway-v1.1
git pull origin infra-scaleway-v1.1
```

**Avant de considérer le merge terminé, vérifier :**
- `backend/.env` de production contient bien `MISTRAL_API_KEY` / `GEMINI_API_KEY`
- `backend/requirements.txt` contient bien `litellm` et `pydantic` (à vérifier — jamais confirmé explicitement en session, voir document *Développements futurs*)
- Passer `status: 'wip'` à `status: 'live'` dans `frontend/app/realisations/page.tsx` une fois le flux production validé

---

## 10. Relancer la migration PostgreSQL (si jamais nécessaire sur un autre environnement)

```bash
psql "$DATABASE_URL" -f migrations/sql/017_gestion_patrimoine_messages.sql
```

Vérification :
```sql
SELECT filename FROM schema_migrations WHERE filename = '017_gestion_patrimoine_messages.sql';
\d gestion_patrimoine_sessions
\d gestion_patrimoine_messages
```

*(Déjà exécutée sur la base Scaleway de référence — inutile de la relancer dessus.)*
