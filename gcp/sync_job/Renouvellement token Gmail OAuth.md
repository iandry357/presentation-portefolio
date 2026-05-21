# Renouvellement token Gmail OAuth

> ⚠️ À effectuer **tous les 7 jours** — l'app OAuth est en mode "Test", le token expire systématiquement.

---

## Prérequis

- `gcloud` CLI installé et authentifié (`gcloud auth login`)
- `gmail_venv` configuré avec `google-auth-oauthlib` et `google-api-python-client`
- Cmder lancé en **Administrateur**

---

## Étapes

### 1. Activer le venv et supprimer l'ancien token local

```bash
cd C:\<chemin_vers_ton_projet>\backend\scripts
gmail_venv\Scripts\activate
del token.json
```

> Supprime l'ancien token local pour forcer le flow OAuth complet.

---

### 2. Générer un nouveau token

```bash
python generate_gmail_token.py
```

> Un navigateur s'ouvre → authentifie-toi avec le compte Gmail concerné.  
> Un nouveau `token.json` est généré dans le répertoire courant.

---

### 3. Vérifier le contenu du token généré

```bash
type token.json
```

> Vérifie que le JSON est bien complet et non vide avant de continuer.

---

### 4. Pousser le nouveau token dans GCP Secret Manager

```bash
gcloud secrets versions add gmail-token \
  --data-file=token.json \
  --project=gen-lang-client-0989575872
```

> Une nouvelle version `ENABLED` du secret `gmail-token` est créée.  
> Le Cloud Run Job récupère toujours la **latest version** automatiquement.

---

### 5. Vérifier que la nouvelle version est active

```bash
gcloud secrets versions list gmail-token \
  --project=gen-lang-client-0989575872
```

> La nouvelle version doit apparaître avec le statut `ENABLED`.  
> Note le numéro de l'ancienne version pour l'étape suivante.

---

### 6. Désactiver l'ancienne version

```bash
gcloud secrets versions disable <ANCIEN_NUMERO_VERSION> \
  --secret=gmail-token \
  --project=gen-lang-client-0989575872
```

> Remplace `<ANCIEN_NUMERO_VERSION>` par le numéro de l'étape 5.  
> ⚠️ Ne pas sauter cette étape — les anciennes versions s'accumulent sinon.

---

## Rappels

| Élément | Valeur |
|---|---|
| Projet GCP | `gen-lang-client-0989575872` |
| Secret token | `gmail-token` |
| Secret credentials | `gmail-credentials` *(ne change pas)* |
| Script local | `backend/scripts/generate_gmail_token.py` |
| Venv dédié | `backend/scripts/gmail_venv/` |
| Fréquence | Tous les 7 jours |

---

## 🔧 Dette technique — Migration à prévoir

> Les fichiers suivants sont actuellement dans `backend/scripts/` pour des raisons historiques.  
> Ils devraient être migrés vers `gcp/sync_job/` pour cohérence architecturale,  
> puisqu'ils appartiennent logiquement au périmètre du Cloud Run Job GCP.

Fichiers concernés :
- `generate_gmail_token.py`
- `gmail_venv/`
- `credentials.json` *(gitignored)*
- `token.json` *(gitignored)*