# Développements futurs — MVP "gestion-patrimoine"

*Points identifiés pendant la session (conception, code, déploiement, debug) qui restent ouverts ou méritent une décision/action ultérieure. Classés par priorité pratique, pas par ordre chronologique.*

---

## 🔴 Bloquants avant merge en production

### 1. Vérifier les dépendances backend
`profil_agent.py` copié dans `backend/routers/gestion_patrimoine/` utilise `litellm` et `pydantic`. **Jamais vérifié explicitement en session** si `backend/requirements.txt` les contient déjà. Si absent, le premier déploiement Scaleway post-merge plantera au chargement du module.
```bash
grep -E "litellm|pydantic" backend/requirements.txt
```

### 2. Variables d'environnement backend Scaleway (production)
`MISTRAL_API_KEY` et `GEMINI_API_KEY` doivent être présentes dans le `.env`/Secret Manager du backend de **production**, pas seulement en local. Le CI/CD ne les ajoute pas automatiquement.

### 3. Décider la stratégie de cohabitation RAM/CPU des `llama-server`
Avec `llama-server-gestion-patrimoine` (Qwen2.5-3B, port 8009) qui s'ajoute à `llama-server` (SG) et `llama-server-sanofi`, le VPS OVH (7,6 Gi RAM observés, 0 swap) est proche de la saturation si les 3 tournent simultanément — déjà observé en session (RAM tendue, obligation d'arrêter SG/Sanofi pour tester). Deux options identifiées, non tranchées :
- **Upgrade VPS** (VPS-3 à 12,24€/mois ou VPS-4 à 23,49€/mois) — simple, pas de changement de code
- **Conteneuriser les `llama-server`** pour les rendre pilotables par l'orchestrateur wake-on-demand existant (option "A" discutée en session : `Dockerfile` minimal autour du binaire + volume `.gguf`, entrée `registry.yaml` de type conteneur comme les `ml-service`) — cohérent avec la philosophie "on-demand plutôt que toujours-allumé" déjà appliquée partout ailleurs, mais demande du travail (build + test + migration de service pour SG et Sanofi aussi, si on veut une cohérence totale)

Sans décision, un merge en l'état risque de reproduire le problème RAM en production dès que 2-3 MVPs sont utilisés simultanément par un visiteur.

---

## 🟠 À investiguer, non bloquant

### 4. Cause racine du timeout `embedding-service` au premier wake
Le tout premier appel `/chat` a échoué avec `TimeoutError: embedding-service indisponible après 60s d'attente`, alors qu'un wake manuel juste après a réussi en quelques secondes. Deux pistes non tranchées :
- `WAKE_TIMEOUT_SEC=60` (dans `ml/config.py`) potentiellement trop court pour un cold start réel (chargement du modèle `sentence-transformers` depuis disque)
- Un problème de séquencement entre le signal `/wake` envoyé par le backend et celui envoyé en interne par `tools.py` (double wake, l'un pourrait avoir échoué silencieusement)

**Action suggérée** : au prochain redémarrage à froid du VPS, surveiller `docker logs embedding-service` dès l'envoi du wake pour mesurer le temps de démarrage réel, et ajuster `WAKE_TIMEOUT_SEC` en conséquence (ex: 90-120s).

### 5. Latence de réponse (~94 secondes mesurées)
Sur le test réel, une réponse complète (recherche + génération) a pris 94s. Leviers identifiés mais non testés :
- `--threads` du service systemd (actuellement 4) — vérifier `nproc` réel sur le VPS et ajuster
- Réduire `-c 4096` si les chunks CGI ne nécessitent pas réellement un contexte aussi large
- Modèle plus petit (1.5B) si la qualité de réponse reste acceptable
- Accepter la latence telle quelle si l'usage reste démo/portfolio (pas de charge concurrente réelle)

### 6. `ram_mb: 300` dans `registry.yaml` — estimation non vérifiée
Valeur posée par extrapolation (le service ne charge aucun modèle lourd, juste du routing HTTP + client ChromaDB léger), jamais confirmée empiriquement. À corriger après un premier cycle de production réel :
```bash
docker stats gestion-patrimoine-ml
```

---

## 🟡 Dette technique assumée, à garder en tête

### 7. Duplication de `profil_agent.py`
Le fichier existe en double : `realisations/gestion-patrimoine/agents/profil_agent.py` (référence, non exécutée) et `backend/routers/gestion_patrimoine/profil_agent.py` (copie réellement exécutée). Toute modification future doit être répercutée manuellement dans les deux — aucun mécanisme de synchronisation automatique. Risque de divergence silencieuse dans le temps.

### 8. Duplication de configuration entre `pipeline/config.py` et `ml/config.py`
Décision assumée dès la conception (images Docker indépendantes) — les deux fichiers dupliquent des constantes ChromaDB/embedding-service similaires sans les partager. Cohérent avec le pattern déjà en place ailleurs dans le portfolio, mais à ne pas oublier si une valeur change d'un côté sans l'autre (ex: `CHROMA_COLLECTION`).

### 9. `chemin_hierarchique` abandonné en cours de pipeline
Prévu dans la fiche projet d'origine, jamais implémenté dans `chroma_loader.py`. Le schéma `ArticleCite` (`assistant_agent.py`) a été corrigé en session pour ne contenir que `numero_article` + `url_source`. Si un jour ce champ est jugé utile (navigation plus fine dans le CGI), il faudra ré-enrichir le chunking **et** re-processer les 761 chunks déjà en base — pas un simple ajout de colonne.

### 10. Pas de reprise de session au rechargement de page (frontend)
Le flux `ProfilGenerator → ChatAssistant` repart de zéro si l'utilisateur recharge la page (pas de `localStorage`/persistance du `session_id` côté client). Décision volontaire pour rester simple, mais si l'usage réel montre que c'est gênant (utilisateur qui perd sa conversation), il faudra ajouter une persistance légère.

### 11. Function calling simulé par prompt (ReAct), pas natif OpenAI-style
Choix assumé pour la robustesse (cohérence avec le pattern SG/Sanofi, indépendance vis-à-vis de la configuration `--jinja` du binaire `llama-server`). Si un futur MVP a besoin de function calling natif plus fiable (modèle plus gros, meilleur binaire `llama.cpp`), il faudra re-tester l'option A (`tools`/`tool_calls`) — jamais validée empiriquement dans ce portfolio à ce stade.

### 12. Pas de test automatisé
Aucun test unitaire/intégration écrit pour `profil_agent`, `assistant_agent`, `tools.py`, ou les routes backend. Tout a été validé manuellement (`curl`, test frontend local). À considérer si le MVP doit devenir plus robuste dans le temps (régression silencieuse possible sur un futur refactor).

---

## 🟢 Améliorations UX possibles (non urgentes)

- Bouton "Nouveau profil" dans `ChatAssistant` pour relancer sans recharger la page
- Indicateur visuel distinct pendant le premier tour (synthèse initiale) vs les tours suivants (déjà un `loading` générique, pourrait être différencié : "Génération de la synthèse initiale..." vs "Recherche dans le référentiel...")
- Afficher le nombre d'itérations de recherche effectuées par `assistant_agent` (actuellement invisible côté frontend, seulement loggé côté `ml-service`)
- Passer `status: 'wip'` → `'live'` sur `/realisations` une fois le merge + test production validés
