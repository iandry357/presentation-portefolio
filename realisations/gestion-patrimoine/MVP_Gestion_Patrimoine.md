# Fichier Projet — MVP "gestion-patrimoine"

*Document de cadrage — à mettre à jour au fil des sessions de conception*

---

## 1. Contexte

Nouveau MVP sectoriel dans le portfolio **Portefolio-CV-FT**.

**Objectif métier du POC** : démontrer un copilote d'ingénierie patrimoniale combinant génération de profils clients synthétiques (RGPD-safe) et analyse fiscale groundée sur des textes de loi réels et traçables (anti-hallucination), avec citation obligatoire de l'article de loi utilisé.

Branche Git : `feature/gestion-patrimoine-mvp` (depuis `infra-scaleway-v1.1`).

---

## 2. Nomenclature validée

| Rôle fonctionnel (spec d'origine) | Nom utilisé dans le projet |
|---|---|
| MVP | `gestion-patrimoine` |
| Agent CRM : génération profil | `profil_agent` |
| Agent Analyste : orchestrateur RAG | `assistant` |
| Base de connaissances juridique | `referentiel_patrimoine` |

Cette nomenclature s'applique partout : répertoires, noms de fichiers, collection ChromaDB, dataset BigQuery, service accounts, registry OVH.

---

## 3. Architecture fonctionnelle

```
[ Open Data Légifrance ]
         │  téléchargement automatisé + chunking par article CGI
         ▼
┌───────────────────────┐
│  referentiel_patrimoine │  ChromaDB (collection dédiée)
│  (chunking + embeddings)│  + BigQuery (dataset dédié, traçabilité/analytics)
└───────────┬─────────────┘   embeddings via embedding-service partagé (port 8004, réutilisé tel quel)
            │ recherche sémantique (tool)
            ▼
┌─────────────────────┐        ┌───────────────────────────────┐
│   profil_agent        │        │         assistant              │
│   Mistral API           │──────▶│  LLM local OVH (Qwen2.5-Instruct│
│   (mistral-small-latest)│ profil│  GGUF, function calling natif) │
│   appel direct depuis   │ client│  chat multi-tours              │
│   le backend             │      │                                 │
└─────────────────────┘        └──────────────┬──────────────────┘
                                                │
                                                ▼
                                    Backend Scaleway
                                    (router gestion_patrimoine)
                                                │
                                                ▼
                                    Frontend
                                    /realisations/gestion-patrimoine
```

**Flux d'interaction** : génération d'un profil client fictif par `profil_agent` → transmission à `assistant` → `assistant` décide s'il appelle l'outil de recherche sur `referentiel_patrimoine` (function calling) → synthèse avec citation d'article obligatoire → conversation multi-tours possible avec `assistant` par la suite.

---

## 4. Décisions techniques actées

| Sujet | Décision |
|---|---|
| Ingestion Légifrance — VALIDÉ | API PISTE, mécanisme final testé avec succès : POST /consult/code/tableMatieres (textId=LEGITEXT000006069577, arbre complet du CGI) → parcours récursif filtré par mots-clés thématiques sur les titres de sections → filtrage etat=VIGUEUR (disponible directement dans l'arbre) → POST /consult/getArticle pour le texte complet (champ `content`). **213 articles collectés** (dans la fourchette estimée 200-350). Le mécanisme /search initial a été abandonné (couverture partielle non exploitable, moreArticlesCount non paginable) |
| Agent profil_agent | Appel API Mistral direct depuis le backend — pas de service dédié |
| Agent assistant | LLM local sur OVH (Qwen2.5-Instruct, GGUF, quantifié) — nécessite function calling natif |
| Serving du LLM local | Binaire `llama-server` partagé, lancé en systemd sur l'hôte OVH (pattern Sanofi/SG) — pas de conteneur Docker dédié pour l'inférence brute |
| Couche orchestration | FastAPI `ml-service` conteneurisé (port **8008**), contient la boucle function calling et appelle `llama-server` en HTTP interne |
| Embeddings RAG | Réutilisation de l'`embedding-service` partagé existant (port 8004) — pas de service dédié |
| Périmètre thématique du référentiel (fixé) | 1. Mutations à titre gratuit — donations/successions (~100-150 art.) · 2. IFI (~20-30 art.) · 3. Plus-values mobilières/immobilières (~80-120 art.) · 4. Assurance-vie — fiscalité successorale (~5-10 art.) · 5. PER / épargne retraite (~10-20 art.) — total estimé 200-350 articles, avant retrait des articles abrogés |
| Cohérence thématique | `profil_agent` doit générer une demande/objectif patrimonial toujours pioché parmi les 5 thématiques couvertes par `referentiel_patrimoine` (donations/successions, IFI, plus-values, assurance-vie, PER) — garantit que `assistant` trouve toujours un article pertinent à citer |
| Mots-clés de filtrage (v1, à affiner après premier crawl) | Donations/successions : "mutation à titre gratuit", "donation", "succession", "droits de mutation" · IFI : "impôt sur la fortune immobilière", "fortune immobilière" · Plus-values : "plus-value", "plus-values" · Assurance-vie : "assurance-vie", "assurance sur la vie" · PER : "plan d'épargne retraite", "épargne retraite" |
| Stockage traçabilité | Table BigQuery dédiée en plus de ChromaDB (comme les autres MVPs) |
| Chunking | 1 chunk = 1 article (citation exacte garantie). Au-delà de ~500 mots, sous-découpage par alinéa/paragraphe (structure I/II/III, 1°/2°...), numéro d'article conservé en métadonnée sur chaque sous-chunk. Métadonnées par chunk : numéro d'article, chemin hiérarchique (Titre/Chapitre/Section), thématique associée, URL source, statut, date de mise à jour |
| Schéma profil_agent | Sortie JSON structuré. Champs communs : thematique (choisie par l'utilisateur ou tirée au sort si absente), age, situation_familiale, patrimoine_global, objectif (texte transmis à assistant). Bloc `details` spécifique à la thématique : donations/successions (lien de parenté, montant), IFI (valeur patrimoine immobilier net), plus-values (nature du bien, montant plus-value), assurance-vie (primes versées, âge du contrat), PER (montant versé, âge de départ retraite envisagé) |
| Session multi-tours | Persisté en PostgreSQL Scaleway existant (celui qui héberge pgvector) — table dédiée, un enregistrement par échange : session_id, role (user/assistant), contenu, horodatage, tokens_entree, tokens_sortie, cout_estime (renseigné uniquement pour les appels profil_agent/Mistral, null pour assistant qui tourne en local sans coût API), latence_ms, articles_cites (métadonnées des sources) |
| Function calling assistant | Boucle — l'agent peut enchaîner plusieurs appels à search_referentiel avant de répondre, s'il juge sa première recherche insuffisante |
| Anti-hallucination | Si aucun article pertinent trouvé dans referentiel_patrimoine, l'assistant refuse explicitement de répondre plutôt que de produire une réponse sans citation |
| search_referentiel | Recherche vectorielle pure via ChromaDB + embedding-service partagé (port 8004) — cohérent avec le pattern RAG des autres MVPs sectoriels, pas de BM25 ni de rerank. Filtré sur la thématique du profil en cours (métadonnée thematique). top_k = 3 résultats renvoyés à l'agent, avec texte du chunk + métadonnées complètes (numéro d'article, chemin hiérarchique, URL source) |
| Endpoint ml-service | Un seul endpoint générique `/chat` — gère aussi bien le premier tour (synthèse initiale à partir du profil) que les tours suivants. Le backend envoie systématiquement l'historique complet + le profil client à chaque appel (ml-service stateless) |
| Format de réponse ml-service | Structuré : texte de la synthèse/réponse + liste séparée des articles cités (métadonnées : numéro d'article, chemin hiérarchique, URL source) — pas de citations uniquement en ligne dans la prose |
| Endpoints backend | POST /gestion-patrimoine/profil (génère profil via profil_agent, crée session, retourne profil + session_id) · POST /gestion-patrimoine/chat (session_id + message, wake ml-service, appelle /chat, stocke et retourne la réponse) |
| Session backend | 1 profil = 1 session — session_id généré par le backend à la création du profil |
| Flux frontend | Séquentiel — ProfilGenerator affiché en premier (sélecteur thématique optionnel + génération), ChatAssistant n'apparaît qu'une fois le profil généré |
| Affichage citations | Articles cités affichés en liens cliquables vers la page officielle Légifrance de chaque article (URL source déjà présente dans les métadonnées renvoyées par search_referentiel) |
| Infra Terraform | `infra/gestion-patrimoine.tf` — SA `pipeline-gestion-patrimoine` + `terraform-gestion-patrimoine`, dataset BigQuery `referentiel_patrimoine` (table `articles_cgi`), rôles IAM minimaux. Pas de bucket GCS ni d'entrée Vertex AI Model Registry (Qwen2.5-Instruct utilisé tel quel, pas de fine-tuning) |
| Intégration OVH | `registry.yaml` — entrée `gestion-patrimoine-ml` (port 8008, réseau `gestion-patrimoine-ml-network`), gérée par l'orchestrateur wake-on-demand · `llama-server-gestion-patrimoine.service` (systemd, hors orchestrateur, tourne en continu) · `orchestrator_client.py` — wake sur les endpoints `/profil` et `/chat` du backend |
| Structure pipeline | Alignée sur le pattern Docker des autres MVPs (SG, Banque de France) : docker-compose.yml + Dockerfile + requirements.txt + constraints.txt + config.py + sous-dossiers collectors/loaders/transformation/validators, exécuté via `docker-compose run --rm` |
| Embeddings pipeline | Appel HTTP à l'embedding-service existant (port 8004) plutôt qu'un sentence-transformers embarqué — cohérence garantie avec le modèle utilisé au moment de la recherche. Le pipeline étant un job ponctuel (pas un service persistant), il appelle directement l'orchestrateur OVH (/wake puis /health) avant d'appeler l'embedding-service, indépendamment du backend |
| Migration PostgreSQL | Fichier `migrations/017_gestion_patrimoine_messages.sql` (suit la numérotation séquentielle existante, dernier fichier étant `016_source_branch_varchar.sql`), table `gestion_patrimoine_messages` (session_id, role, contenu, tokens_entree, tokens_sortie, cout_estime, latence_ms, articles_cites). Tous les échanges enregistrés (profil_agent ET assistant) — cout_estime = 0 explicite (pas NULL) pour les lignes assistant (LLM local, pas de coût API), tokens/latence toujours trackés. INSERT INTO schema_migrations (filename) VALUES ('017_gestion_patrimoine_messages.sql') en fin de fichier, comme les migrations précédentes |

---

## 5. Arborescence validée

```
realisations/gestion-patrimoine/
├── pipeline/
│   ├── docker-compose.yml
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── constraints.txt
│   ├── config.py
│   ├── orchestrator.py
│   ├── __init__.py
│   ├── collectors/
│   │   ├── __init__.py
│   │   └── legifrance_collector.py
│   ├── loaders/
│   │   ├── __init__.py
│   │   ├── bigquery_loader.py
│   │   └── chroma_loader.py
│   ├── transformation/
│   │   ├── __init__.py
│   │   └── chunking.py
│   └── validators/
│       └── __init__.py
├── agents/
│   ├── profil_agent.py
│   ├── assistant_agent.py
│   └── tools.py
├── ml/
│   ├── main.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── models/                # .gguf transféré par scp, non commité
└── scripts/
    └── check_data.py

backend/routers/gestion_patrimoine/
├── router.py
└── schemas.py

frontend/app/realisations/gestion-patrimoine/
├── page.tsx
└── components/
    ├── ProfilGenerator.tsx
    └── ChatAssistant.tsx

infra/gestion-patrimoine.tf
```