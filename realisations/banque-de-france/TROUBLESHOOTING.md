# MVP Banque de France — Troubleshooting

Incidents rencontrés et résolus pendant la construction du MVP, dans l'ordre chronologique approximatif. Même format que les autres MVPs du projet (`Problèmes majeurs & fixes — Portefolio 1.md`).

---

## Chemins GCS avec antislash Windows (classification)

**Sévérité :** Bloquant (au moment du déploiement d'inférence)

**Symptôme**
`gsutil ls "gs://.../embedding_body/"` renvoyait `CommandException: One or more URLs matched no objects.` alors que `gsutil ls -r` listait bien des fichiers "dans" ce préfixe.

**Cause racine**
`register_model.py` construisait les noms d'objets GCS avec `file_path.relative_to(artifact_dir)` inséré directement dans une f-string. Sous Windows, `str()` sur un `Path` restitue le séparateur natif (`\`), pas `/`. Les objets étaient donc stockés avec des antislashs littéraux dans leur nom — pas une vraie hiérarchie de dossiers, juste un caractère parmi d'autres pour GCS.

**Fix**
```python
relative = file_path.relative_to(artifact_dir).as_posix()
```
Nettoyage du bucket (suppression des objets mal nommés) puis ré-upload avant de considérer le modèle correctement enregistré.

**Leçon**
Toute construction de chemin destinée à un système non-Windows (cloud storage, URL) doit passer par `.as_posix()`, jamais par une f-string directe sur un `Path` sous Windows.

---

## Incompatibilité torch / transformers / sentence-transformers en inférence

**Sévérité :** Bloquant

**Symptôme**
```
NameError: name 'torch' is not defined
```
puis, après un premier correctif trop conservateur :
```
ModuleNotFoundError: No module named 'sentence_transformers.base'
```

**Cause racine**
Le modèle a été entraîné localement avec des versions très récentes (`sentence-transformers==5.6.0`, `transformers==5.14.1`, torch nightly GPU `2.12.0.dev...+cu128`). Le service d'inférence, construit par analogie avec le `requirements.txt` de SG (`transformers==4.40.0`, bien plus ancien), ne pouvait pas désérialiser l'artefact (`modules.json` référence des classes internes absentes des anciennes versions).

**Fix**
- Aligner `sentence-transformers`/`transformers` sur les versions **exactes** de l'entraînement (vérifiées via `pip show` en local, jamais supposées)
- Ne **pas** figer torch à une version précise côté service — installer la dernière stable CPU (`torch` sans version), le nightly GPU d'entraînement n'ayant de toute façon aucun équivalent CPU figé.

**Leçon**
Ne jamais copier un `requirements.txt` d'un autre service par analogie pour des dépendances ML sensibles à la version — toujours vérifier les versions réellement utilisées à l'entraînement.

---

## Collision de nom de projet `docker-compose` (dossiers `ml/` homonymes)

**Sévérité :** Significatif

**Symptôme**
```
ERROR: for ml_ml-service_1  'ContainerConfig'
```
au tout premier `docker-compose up` de `banque-ml`, avec un nom de container (`ml_ml-service_1`) qui s'est avéré être celui de **Sanofi**.

**Cause racine**
`docker-compose` v1 déduit le nom de projet par défaut à partir du nom du **dossier courant**, pas du chemin complet. `realisations/banque-de-france/ml/` et `realisations/sanofi/ml/` ont le même nom de dossier (`ml`) — sans `-p` explicite, `docker-compose` a confondu les deux projets.

**Fix**
Toujours utiliser un nom de projet explicite pour les commandes manuelles sur ce type de service :
```bash
docker-compose -p banque-de-france-ml build --no-cache
```
Pas de fix permanent nécessaire côté `.env`/`COMPOSE_PROJECT_NAME` — vérifié que l'orchestrateur OVH n'utilise **jamais** `docker-compose` (SDK Docker Python direct, `docker_client.py`), donc ce risque ne concerne que les commandes manuelles, pas le fonctionnement en prod.

---

## Bug `docker-compose` v1.29.2 — `KeyError: 'ContainerConfig'` (récurrent)

**Sévérité :** Bloquant (contourné, non résolu à la racine)

**Symptôme**
Le même `KeyError: 'ContainerConfig'` réapparaît sur **tout** `docker-compose up`/`restart` qui doit recréer un container existant sur ce VPS — y compris après avoir corrigé la collision de nom ci-dessus, et y compris sur un container appartenant clairement à Banque de France (`banque-ml-service`, nom sans ambiguïté).

**Cause probable**
Incompatibilité entre `docker-compose` v1.29.2 (abandonné par Docker depuis longtemps) et une version récente du moteur Docker Engine installé sur le VPS — le format retourné par `docker inspect` a changé, et cette vieille version de compose ne sait plus le lire pour décider s'il faut recréer un container.

**Fix (contournement, pas une résolution)**
Ne jamais utiliser `docker-compose up`/`restart` pour (re)créer un container sur ce VPS. Builder via compose (fonctionne), puis démarrer via `docker run` direct :
```bash
docker-compose -p banque-de-france-ml build --no-cache
docker rm -f banque-ml-service
docker run -d --name banque-ml-service -p 8007:8007 -v ... --env-file .env banque-de-france-ml_ml-service:latest
```

**Non résolu — backlog**
Aucun autre MVP n'avait rencontré ce bug avant aujourd'hui malgré des mois de `docker-compose up` répétés, ce qui suggère une régression **récente** côté environnement OVH (mise à jour automatique du moteur Docker), pas une incompatibilité de toujours. À investiguer : mettre à jour `docker-compose` vers une version compatible (ou migrer vers `docker compose` v2, intégré au CLI Docker moderne) — risque latent pour **tous** les MVPs, pas seulement Banque de France, le jour où un de leurs containers devra être recréé.

---

## Container Sanofi renommé automatiquement par Docker — désynchronisé de `registry.yaml`

**Sévérité :** Significatif (découvert incidemment, pas causé par la session du jour)

**Symptôme**
En tentant de diagnostiquer le bug ci-dessus sur Sanofi, découverte que le vrai nom du container en cours d'exécution était `6f8876e54cfc_ml_ml-service_1` (préfixé par un hash), alors que `registry.yaml` déclare `container_name: ml_ml-service_1` (sans préfixe). `docker ps --filter name=...` (recherche par sous-chaîne) masquait le problème ; le SDK Docker utilisé par l'orchestrateur (`client.containers.get(container_name)`, correspondance exacte) ne le pouvait pas.

**Conséquence potentielle**
L'orchestrateur ne pouvait probablement plus réveiller Sanofi correctement depuis un moment (`NotFound` silencieux dans `docker_client.py`), sans qu'aucune alerte ne remonte.

**Fix**
```bash
docker rename 6f8876e54cfc_ml_ml-service_1 ml_ml-service_1
```

**Leçon**
`docker ps --filter name=X` n'est pas une preuve que le nom **exact** `X` existe — seulement qu'un container dont le nom **contient** `X` existe. À vérifier avec `docker inspect <nom_exact>` en cas de doute sur un service piloté par l'orchestrateur.

---

## `registry.yaml` modifié mais non pris en compte avant restart de l'orchestrateur

**Sévérité :** Mineur

**Symptôme**
Après avoir édité `registry.yaml` (renommage `sg-embedding` → `embedding-service`), `GET /status` continuait d'afficher l'ancienne clé.

**Cause**
Le fichier est monté en volume `:ro` (pas copié dans l'image), donc `load_registry()` le relit bien à chaque appel côté code — mais le montage lui-même semble mis en cache par Docker tant que le container n'est pas redémarré.

**Fix**
```bash
docker restart ovh-orchestrator
```

---

## Doublons dans la veille (BigQuery + Topic Modeling)

**Sévérité :** Significatif (qualité des données, pas un crash)

**Symptôme**
Plusieurs occurrences du même article dans `/news`, et un total de documents exploitables anormalement élevé côté Topic Modeling (143, avant correction).

**Cause racine**
L'`id` de chaque article est généré depuis le titre brut — une variation mineure de formatage du titre entre deux runs RSS produit un ID différent pour un article par ailleurs identique, empêchant la déduplication naturelle par clé primaire.

**Fix (au niveau lecture, pas réingestion)**
Déduplication par titre normalisé (espaces réduits, casse ignorée), en gardant la ligne la plus récente :
```sql
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY LOWER(TRIM(REGEXP_REPLACE(title, r'\s+', ' ')))
    ORDER BY ingested_at DESC
) = 1
```
Appliqué à la fois côté `backend/routers/banque_de_france/router.py` (`/stats`, `/news`) et côté `ml/bq_client.py` (Topic Modeling) — deux points de lecture distincts de la même table, chacun nécessitant le fix séparément.

**Piège rencontré en cours de route**
`QUALIFY` combiné à `COUNT(*)` au même niveau échoue (`PARTITION BY expression references column title which is neither grouped nor aggregated`) — BigQuery traite alors la requête comme un agrégat global. Fix : envelopper la déduplication dans une sous-requête, agréger seulement sur son résultat.

**Non traité**
Les doublons potentiellement présents dans ChromaDB (même cause racine, IDs différents pour le même article) n'ont pas été vérifiés — RAG jugé satisfaisant tel quel, priorité laissée en backlog.

---

## Variable de configuration manquante (`GCP_SERVICE_ACCOUNT_JSON_BANQUE`)

**Sévérité :** Bloquant (bref)

**Symptôme**
```
RuntimeError: GCP_SERVICE_ACCOUNT_JSON_BANQUE non configuré
```
sur `/banque-de-france/stats` et `/news`.

**Cause**
`app/core/config.py` (Pydantic Settings) ne déclarait pas cette variable — supposée par analogie avec `GCP_SERVICE_ACCOUNT_JSON_SG`, jamais vérifiée avant l'implémentation initiale du router.

**Fix**
Ajout du champ dans `Settings`, puis renseignement de la valeur réelle (JSON compacté sur une ligne) dans `backend/.env` local et dans le secret GitHub `TF_VARS_FILE` pour la CI.

**Leçon**
Toujours vérifier l'existence d'une variable de configuration supposée avant d'écrire du code qui en dépend, plutôt que de découvrir l'absence au runtime.

---

## `Dockerfile` ne copiait pas le dossier `data/` (exemples de démo manquants)

**Sévérité :** Mineur

**Symptôme**
`GET /predict/classification/examples` renvoyait systématiquement une liste vide, sans erreur.

**Cause**
`COPY *.py ./` dans le `Dockerfile` ne prend que les fichiers Python à la racine — `demo.csv` (dans `data/`) n'était jamais copié dans l'image. Le code gérait l'absence du fichier avec un simple warning silencieux, jamais remonté à l'utilisateur.

**Fix**
```dockerfile
COPY data ./data
```

**Leçon**
Un fallback silencieux (warning au lieu de crash) est une bonne pratique de robustesse, mais peut masquer un vrai problème de build pendant longtemps si personne ne relit les logs — envisager un log plus visible (niveau ERROR) quand l'absence d'un fichier attendu dégrade fonctionnellement une route entière.

---

## `curl` sous Cmder/Windows — guillemets simples non interprétés

**Sévérité :** Mineur

**Symptôme**
```
curl: (6) Could not resolve host: application
curl: (3) URL rejected: Bad hostname
```
sur une commande `curl -d '{"question": "..."}'` par ailleurs correcte.

**Cause**
Windows n'interprète pas les guillemets simples comme des délimiteurs de chaîne — la commande a été fractionnée mot par mot par le shell.

**Fix**
Guillemets doubles avec échappement interne :
```bash
curl -d "{\"question\": \"...\"}"
```
