# Upload CV PDF → PostgreSQL

> Script à lancer manuellement à chaque mise à jour du CV.  
> Stocke le PDF brut + les images PNG (300 DPI) en base PostgreSQL Scaleway.

---

## Prérequis

- Python avec les dépendances installées :
  - `psycopg2`
  - `PyMuPDF` (`fitz`)
  - `Pillow`
- L'URL de connexion PostgreSQL Scaleway (disponible dans Scaleway Secret Manager ou `.env` local)
- Le fichier PDF du CV présent localement

---

## Tables créées automatiquement

Le script crée les tables si elles n'existent pas encore.

| Table | Contenu |
|---|---|
| `cv_files` | PDF brut (filename, content_type, file_data BYTEA) |
| `cv_pages` | Images PNG par page (page_number, image_data BYTEA, width, height) |

---

## Commande

```bash
cd C:\<chemin_vers_ton_projet>\backend
python scripts/upload_cv_pdf.py \
  --database-url="postgresql://user:pwd@host:port/db" \
  --pdf-path="documents/resume.pdf"
```

Commande pour Scaleway

```bash
python scripts/upload_cv_pdf.py \
  --database-url="postgresql+asyncpg://portefolio-credential:PWD@IP:PORT/rdb?ssl=require" \
  --pdf-path="scripts/IandryRakotoniaina_IngenieurRD_DataIA_2026.pdf"
```

> `--pdf-path` est optionnel — valeur par défaut : `documents/resume.pdf`

---

## Comportement

1. Connexion à PostgreSQL
2. Création des tables `cv_files` et `cv_pages` si absentes
3. Si un CV existe déjà → confirmation manuelle demandée avant écrasement
4. Upload du PDF brut dans `cv_files`
5. Conversion page par page en PNG 300 DPI via PyMuPDF
6. Stockage de chaque image dans `cv_pages`

---

## Exemple de sortie attendue

```
🔌 Connexion à la base...
✅ Tables cv_files et cv_pages créées/vérifiées
⚠️  Un CV existe déjà. Écraser ? (y/N) : y
🗑️  CV et pages existants supprimés
✅ CV PDF uploadé : resume.pdf (XXXXX bytes)
🔄 Conversion PDF → Images PNG (300 DPI)...
📄 2 page(s) détectée(s)
  ✅ Page 1 : 2480x3508px (XXXKB)
  ✅ Page 2 : 2480x3508px (XXXKB)
✅ 2 image(s) stockée(s) en base de données
✅ Terminé !
```

---

## Rappels

| Élément | Valeur |
|---|---|
| Script | `backend/scripts/upload_cv_pdf.py` |
| PDF source par défaut | `documents/resume.pdf` |
| Destination | PostgreSQL Scaleway |
| Tables impactées | `cv_files`, `cv_pages` |

---

## 🔧 Dette technique — Migration à prévoir

> Le PDF est actuellement stocké directement en base (BYTEA).  
> La cible architecturale est **Object Storage Scaleway** (bucket S3-compatible, Terraform prêt).  
> La migration impliquera de remplacer `file_data BYTEA` par une URL de référence vers le bucket.  
> Ce chantier est bloqué par **Chantier 1E** (Upload CV — dépend 1A/1B/1C/1D).