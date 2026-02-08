#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seed_data.py - Seed + embeddings Voyage AI + insertion directe PostgreSQL
Génère aussi init.sql en backup
"""

import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Tuple
import time
import hashlib
import argparse
import chardet
from litellm import embedding

try:
    from voyageai import Client as VoyageClient
    import psycopg2
    from psycopg2.extensions import adapt, AsIs
except ImportError as e:
    print(f"Paquets manquants : {e}")
    print("pip install voyageai psycopg2-binary")
    sys.exit(1)

# ────────────────────────────────────────────────
#  CONFIGURATION
# ────────────────────────────────────────────────

VOYAGE_MODEL       = "voyage-3"              # → 1024 dim fixe
EMBEDDING_DIM      = 1024
BATCH_SIZE_EMBED   = 3
SLEEP_BETWEEN_CALLS = 2

# Racine du projet dans le conteneur
PROJECT_ROOT = "/app"

DATA_DIR = os.path.join(PROJECT_ROOT, "scripts", "data")

FILES = {
    "experiences": os.path.join(DATA_DIR, "experiences.json"),
    "formations":  os.path.join(DATA_DIR, "formations.json"),
    "skills":      os.path.join(DATA_DIR, "skills.json"),
    "informations":      os.path.join(DATA_DIR, "informations.json"),
}

OUTPUT_SQL = os.path.join(PROJECT_ROOT, "scripts", "init.sql")
EMBEDDINGS_CACHE = os.path.join(PROJECT_ROOT, "scripts", "embeddings_cache.json")

DB_PARAMS = {
    "host":     os.getenv("POSTGRES_HOST", "postgres"),
    "port":     int(os.getenv("POSTGRES_PORT", "5432")),
    "dbname":   os.getenv("POSTGRES_DB", "portfolio_rag"),
    "user":     os.getenv("POSTGRES_USER", "postgresDefault"),
    "password": os.getenv("POSTGRES_PASSWORD", "postgresDefault"),
    "client_encoding": "UTF8", 
}

VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
if not VOYAGE_API_KEY:
    print("VOYAGE_API_KEY manquante dans l'environnement")
    sys.exit(1)

# ────────────────────────────────────────────────
#  Helpers
# ────────────────────────────────────────────────

def pg_quote(value):
    """
    Échappe proprement pour PostgreSQL via psycopg2.adapt()
    """
    if value is None or value == "":
        return "NULL"

    value = value.encode('ascii', errors='ignore').decode('ascii')
    adapted = adapt(value)
    # Gestion robuste de l'encodage pour caractères français
    quoted = adapted.getquoted()
    if isinstance(quoted, bytes):
        try:
            return quoted.decode('utf-8', errors='replace')
        except UnicodeDecodeError:
            return quoted.decode('latin-1', errors='replace')
    return str(quoted)

# from psycopg2.extensions import adapt, AsIs
# import os

# def pg_quote(value):
#     """
#     Échappe proprement pour PostgreSQL via psycopg2.adapt()
#     Fonctionne même sans connexion active (fallback manuel)
#     """
#     if value is None or value == "":
#         return "NULL"

#     if not isinstance(value, (str, bytes)):
#         value = str(value)

#     try:
#         # Tentative normale
#         adapted = adapt(value)
#         quoted = adapted.getquoted()

#         if isinstance(quoted, bytes):
#             # Avec connexion → UTF-8
#             # Sans connexion → peut être latin-1 ou autre → on force UTF-8 safe
#             return quoted.decode('utf-8', errors='surrogateescape')
        
#         return quoted  # déjà str

#     except UnicodeEncodeError:
#         # Cas où latin-1 est tenté en interne → fallback manuel sûr
#         # On échappe nous-mêmes (équivalent à ce que ferait psycopg2 en UTF-8)
#         if isinstance(value, bytes):
#             value = value.decode('utf-8', errors='replace')
        
#         escaped = value.replace("'", "''").replace("\\", "\\\\")
#         return f"E'{escaped}'"   # E'' = échappement standard + UTF-8

#     except Exception as e:
#         # Tout autre erreur inattendue → fallback
#         escaped = str(value).replace("'", "''").replace("\\", "\\\\")
#         return f"E'{escaped}'"


def pg_array(arr: List[str]) -> str:
    """
    Transforme une liste Python en ARRAY PostgreSQL
    """
    if not arr:
        return "ARRAY[]::text[]"
    escaped = [pg_quote(item).strip("'") for item in arr]
    return "ARRAY[" + ",".join(f"'{e}'" for e in escaped) + "]::text[]"


def pg_vector(vec: List[float]) -> str:
    """
    Transforme une liste de floats en vecteur pgvector
    """
    return f"'[{','.join(f'{x:.7f}' for x in vec)}]'::vector"

def detect_encoding(file_path: str) -> str:
    with open(file_path, "rb") as f:
        raw_data = f.read(10000)  # Lit les 10 000 premiers octets pour la détection
        return chardet.detect(raw_data)["encoding"]

def load_json(path: str) -> list:
    if not os.path.exists(path):
        print(f"Fichier absent : {path}")
        return []
    encoding = detect_encoding(path)
    with open(path, encoding=encoding, errors="replace") as f:
    # with open(path, encoding="utf-8") as f:
        return json.load(f)

def normalize_skill_key(s: Dict) -> Tuple[str, str, str]:
    name = (s.get("name") or "").strip().lower()
    cat  = (s.get("category") or "Autres").strip()
    lvl  = (s.get("proficiency_level") or "Intermédiaire").strip()
    return name, cat, lvl


def collect_unique_skills(exps: List, forms: List, globals_sk: List) -> List[Dict]:
    seen = {}
    for source in [globals_sk, *[e.get("skills", []) for e in exps], *[p.get("skills", []) for e in exps for p in e.get("projects", [])]]:
        for item in source:
            if isinstance(item, str):
                sk = {"name": item.strip(), "category": "Programmation", "proficiency_level": "Intermédiaire"}
            else:
                sk = item
            key = normalize_skill_key(sk)
            if key not in seen:
                seen[key] = sk
    return list(seen.values())

def text_information(exp: Dict) -> str:
    
    parts = [
        f"Je suis {str(exp.get('prenom',''))} {str(exp.get('nom',''))}, avec mon prénom qui se prononce {exp.get('prononciation')} ",
        f"Je suis née à {exp.get('pays_naissance')} le {exp.get('date_naissance')}",
        f"Je suis arrivé en {exp.get('location')} en 2015",
        f"En plus de ma grande passion pour l'informatique, je suis également {exp.get('passion')}"
    ]
    return " | ".join(filter(None, parts)) or "Informations sociales"

def text_experience(exp: Dict) -> str:
    parts = [
        f"Date : {str(exp.get('start_date',''))} à {str(exp.get('end_date',''))}",
        f"Entreprise : {exp.get('company','')}, {exp.get('location')}",
        f"Rôle : {exp.get('role','')}",
        f"Type : {exp.get('mission_type','')}",
        exp.get("context", ""),
        exp.get("projects", [])[0].get('objective', ''),
        exp.get("projects", [])[0].get('problem', ''),
        exp.get("projects", [])[0].get('solution', ''),
        exp.get("projects", [])[0].get('results', ''),
        exp.get("projects", [])[0].get('impact', ''),
        # exp['projects']['problem'],
        # exp['projects']['solution'],
        # exp['projects']['results'],
        # exp['projects']['impact'],
        f"Technologies : {', '.join(exp.get('technologies',[]))}",
    ]
    return " | ".join(filter(None, parts)) or "Expérience professionnelle"


def text_project(proj: Dict) -> str:
    parts = [
        f"Projet : {proj.get('name','')}",
        f"Date : {str(proj.get('start_date',''))} à {str(proj.get('end_date',''))}",
        proj.get("description", ""),
        f"Objectif : {proj.get('objective','')}",
        f"Problème : {proj.get('problem','')}",
        f"Solution : {proj.get('solution','')}",
        f"Résultats : {proj.get('results','')}",
        f"Impact : {proj.get('impact','')}",
        f"Stack : {proj.get('stack','')}",
    ]
    return " | ".join(filter(None, parts)) or "Projet"


def text_formation(form: Dict) -> str:
    parts = [
        f"{form.get('degree','')} à {form.get('institution','')}",
        f"Date : {str(form.get('start_date',''))} à {str(form.get('end_date',''))}",
        f"Domaine : {form.get('field','')}",
        form.get("description", ""),
        f"Apprentissages clés : {form.get('key_learnings','')}",
    ]
    return " | ".join(filter(None, parts)) or "Formation"


def text_hash(text: str) -> str:
    """
    Génère un hash MD5 du texte pour cache
    """
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def load_embeddings_cache() -> Dict:
    """
    Charge le cache d'embeddings depuis le fichier JSON
    """
    if not os.path.exists(EMBEDDINGS_CACHE):
        return {}
    
    try:
        with open(EMBEDDINGS_CACHE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  Erreur lecture cache : {e}")
        return {}


def save_embeddings_cache(cache: Dict):
    """
    Sauvegarde le cache d'embeddings dans le fichier JSON
    """
    try:
        with open(EMBEDDINGS_CACHE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        print(f"✓ Cache sauvegardé dans {EMBEDDINGS_CACHE}")
    except Exception as e:
        print(f"⚠️  Erreur sauvegarde cache : {e}")


def get_embeddings(texts: List[str], modelEmbeddings: str, use_cache: bool = True) -> List[List[float]]:
    if not texts:
        return []
    
    # Charger le cache existant
    cache = load_embeddings_cache() if use_cache else {}
    
    embs = []
    texts_to_compute = []
    indices_to_compute = []
    
    # Vérifier quels textes sont dans le cache
    for i, text in enumerate(texts):
        text_id = text_hash(text)
        if use_cache and text_id in cache:
            embs.append(cache[text_id])
        else:
            embs.append(None)  # Placeholder
            texts_to_compute.append(text)
            indices_to_compute.append(i)
    
    # Calculer les embeddings manquants
    if texts_to_compute:
        print(f"🔄 Calcul de {len(texts_to_compute)} embeddings (cache: {len(texts) - len(texts_to_compute)})")

        if modelEmbeddings == "voyage":
            client = VoyageClient(api_key=VOYAGE_API_KEY)
        # if modelEmbeddings == "mistral"
        
        computed_embs = []
        for i in range(0, len(texts_to_compute), BATCH_SIZE_EMBED):
            batch = texts_to_compute[i:i+BATCH_SIZE_EMBED]
            try:
                if modelEmbeddings == "voyage":
                    resp = client.embed(batch, model=VOYAGE_MODEL, input_type="document")
                    computed_embs.extend(resp.embeddings)
                if modelEmbeddings == "mistral":
                    response = embedding(model="mistral/mistral-embed", input=batch)
                    embeddings = [d["embedding"] for d in response.data] 
                    # embeddings = response.data[0]['embedding']
                    computed_embs.extend(embeddings)





                # computed_embs.extend(resp.embeddings)
            except Exception as e:
                print(f"✗ Erreur embedding batch {i//BATCH_SIZE_EMBED +1}: {e}")
                computed_embs.extend([[0.0]*EMBEDDING_DIM for _ in batch])

            # Respecter le rate limit
            # if i + BATCH_SIZE_EMBED < len(texts_to_compute):
            #     time.sleep(20)
            time.sleep(SLEEP_BETWEEN_CALLS)
        # Mettre à jour le cache et les résultats
        for idx, computed_emb, text in zip(indices_to_compute, computed_embs, texts_to_compute):
            embs[idx] = computed_emb
            cache[text_hash(text)] = computed_emb
        
        # Sauvegarder le cache mis à jour
        if use_cache:
            save_embeddings_cache(cache)
    else:
        print(f"✓ Tous les embeddings trouvés dans le cache")

    return embs


# ────────────────────────────────────────────────
#  SQL generation avec bloc PL/pgSQL
# ────────────────────────────────────────────────

def generate_sql_file(infos, exps, forms, all_skills, info_embs, exp_embs, proj_embs, form_embs, proj_list):
    """
    Génère init.sql avec bloc DO $$ pour utiliser des variables temporaires
    """
    lines = []
    lines.append(f"-- init.sql - généré le {datetime.now():%Y-%m-%d %H:%M:%S}")
    lines.append("BEGIN;")
    lines.append("")
    
    # Bloc PL/pgSQL avec DECLARE
    lines.append("DO $$")
    lines.append("DECLARE")
    
    # Déclarer variables pour experiences
    for i in range(len(exps)):
        lines.append(f"  exp_id_{i} INTEGER;")
    
    # Déclarer variables pour projects
    for i in range(len(proj_list)):
        lines.append(f"  proj_id_{i} INTEGER;")
    
    lines.append("BEGIN")
    lines.append("")

    # 1. SKILLS ────────────────────────────────────────
    lines.append("  -- 1. Skills (ON CONFLICT name)")
    for sk in all_skills:
        n = pg_quote(sk["name"])
        c = pg_quote(sk.get("category", "Autres"))
        l = pg_quote(sk.get("proficiency_level", "Intermédiaire"))
        lines.append(
            f"  INSERT INTO skills (name, category, proficiency_level) "
            f"VALUES ({n}, {c}, {l}) ON CONFLICT (name) DO UPDATE "
            f"SET category = EXCLUDED.category, proficiency_level = EXCLUDED.proficiency_level;"
        )
    lines.append("")

    # 2. INFORMATION avec RETURNING INTO ───────────────
    lines.append("  -- 1.1. Informations")
    for i, info in enumerate(infos):
        nom = pg_quote(info.get("nom"))
        prenom = pg_quote(info.get("prenom"))
        prononciation = pg_quote(info.get("prononciation"))
        date_naissance = f"'{info['date_naissance']}'" if info.get("date_naissance") else "NULL"
        pays_naissance = pg_quote(info.get("pays_naissance"))
        loc = pg_quote(info.get("location", ""))
        passion = pg_quote(info.get("passion", ""))
        embedding = pg_vector(info_embs[i]) if len(info_embs) > 0 else " "
        
        lines.append(
            f"  INSERT INTO informations (nom, prenom, prononciation, date_naissance, pays_naissance, "
            f"location, passion, embedding) "
            f"VALUES ({nom}, {prenom}, {prononciation}, {date_naissance}, {pays_naissance}, "
            f"{loc}, {passion}, {embedding});"
        )

    lines.append("")

    # 2. EXPERIENCES avec RETURNING INTO ───────────────
    lines.append("  -- 2. Experiences")
    for i, exp in enumerate(exps):
        company = pg_quote(exp.get("company"))
        role = pg_quote(exp.get("role"))
        mission_type = pg_quote(exp.get("mission_type", ""))
        start_date = f"'{exp['start_date']}'" if exp.get("start_date") else "NULL"
        end_date = f"'{exp['end_date']}'" if exp.get("end_date") else "NULL"
        duration = exp.get("duration_months", "NULL")
        location = pg_quote(exp.get("location", ""))
        context = pg_quote(exp.get("context", ""))
        techs = pg_array(exp.get("technologies", []))
        embedding = pg_vector(exp_embs[i]) if len(exp_embs) > 0 else " "
        
        lines.append(
            f"  INSERT INTO experiences (company, role, mission_type, start_date, end_date, "
            f"duration_months, location, context, technologies, embedding) "
            f"VALUES ({company}, {role}, {mission_type}, {start_date}, {end_date}, "
            f"{duration}, {location}, {context}, {techs}, {embedding}) "
            f"RETURNING id INTO exp_id_{i};"
        )

    lines.append("")

    # 3. FORMATIONS ────────────────────────────────────
    lines.append("  -- 3. Formations")
    for i, form in enumerate(forms):
        inst = pg_quote(form.get("institution"))
        deg = pg_quote(form.get("degree"))
        field = pg_quote(form.get("field", ""))
        start_date = f"'{form['start_date']}'" if form.get("start_date") else "NULL"
        end_date = f"'{form['end_date']}'" if form.get("end_date") else "NULL"
        loc = pg_quote(form.get("location", ""))
        desc = pg_quote(form.get("description", ""))
        learn = pg_quote(form.get("key_learnings", ""))
        embedding = pg_vector(form_embs[i]) if len(form_embs) > 0 else " "
        
        lines.append(
            f"  INSERT INTO formations (institution, degree, field, start_date, end_date, "
            f"location, description, key_learnings, embedding) "
            f"VALUES ({inst}, {deg}, {field}, {start_date}, {end_date}, "
            f"{loc}, {desc}, {learn}, {embedding});"
        )

    lines.append("")

    # 4. PROJECTS + project_skills ─────────────────────
    lines.append("  -- 4. Projects + project_skills")
    for proj_idx, (exp_idx, proj) in enumerate(proj_list):
        name = pg_quote(proj.get("name"))
        desc = pg_quote(proj.get("description", ""))
        objective = pg_quote(proj.get("objective", ""))
        problem = pg_quote(proj.get("problem", ""))
        solution = pg_quote(proj.get("solution", ""))
        results = pg_quote(proj.get("results", ""))
        impact = pg_quote(proj.get("impact", ""))
        stack = pg_quote(proj.get("stack", ""))
        start_date = f"'{proj['start_date']}'" if proj.get("start_date") else "NULL"
        end_date = f"'{proj['end_date']}'" if proj.get("end_date") else "NULL"
        duration = proj.get("duration_months", "NULL")
        collabs = pg_quote(proj.get("collaborators", ""))
        proj_type = pg_quote(proj.get("project_type", ""))
        embedding = pg_vector(proj_embs[proj_idx]) if len(proj_embs) > 0 else " "
        
        lines.append(
            f"  INSERT INTO projects (experience_id, name, description, objective, problem, "
            f"solution, results, impact, stack, start_date, end_date, duration_months, "
            f"collaborators, project_type, embedding) "
            f"VALUES (exp_id_{exp_idx}, {name}, {desc}, {objective}, {problem}, {solution}, "
            f"{results}, {impact}, {stack}, {start_date}, {end_date}, {duration}, "
            f"{collabs}, {proj_type}, {embedding}) "
            f"RETURNING id INTO proj_id_{proj_idx};"
        )

        # project_skills relations
        for sk_raw in proj.get("skills", []):
            sk_name = sk_raw if isinstance(sk_raw, str) else sk_raw.get("name", "")
            sk_name = sk_name.strip()
            if sk_name:
                sk_quoted = pg_quote(sk_name)
                lines.append(
                    f"  INSERT INTO project_skills (project_id, skill_id) "
                    f"  SELECT proj_id_{proj_idx}, id FROM skills WHERE name = {sk_quoted} "
                    f"  ON CONFLICT DO NOTHING;"
                )

    lines.append("")

    # 5. experience_skills ─────────────────────────────
    lines.append("  -- 5. experience_skills")
    for i, exp in enumerate(exps):
        for sk_raw in exp.get("skills", []):
            sk_name = sk_raw if isinstance(sk_raw, str) else sk_raw.get("name", "")
            sk_name = sk_name.strip()
            if sk_name:
                sk_quoted = pg_quote(sk_name)
                lines.append(
                    f"  INSERT INTO experience_skills (experience_id, skill_id) "
                    f"  SELECT exp_id_{i}, id FROM skills WHERE name = {sk_quoted} "
                    f"  ON CONFLICT DO NOTHING;"
                )

    lines.append("")
    lines.append("END $$;")
    lines.append("")
    lines.append("COMMIT;")

    sql_content = "\n".join(lines)
    
    # Sauvegarde backup
    sql_content = sql_content.encode("utf-8", errors="replace").decode("utf-8")
    with open(OUTPUT_SQL, "w", encoding="utf-8") as f:
        f.write(sql_content)
    print(f"✓ {OUTPUT_SQL} généré")
    
    return sql_content


def execute_sql(sql_content: str):
    """
    Exécute le SQL directement dans PostgreSQL
    """
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute(sql_content)
        conn.commit()
        print("✓ Insertion directe réussie dans PostgreSQL")
    except Exception as e:
        print(f"✗ Erreur lors de l'insertion : {e}")
        print(f"→ Utilisez manuellement : psql -f {OUTPUT_SQL}")
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()


def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description="Seed database avec embeddings Voyage AI")
    parser.add_argument('--force-recompute', action='store_true',
                       help="Forcer le recalcul de tous les embeddings (ignorer le cache)")
    parser.add_argument(
        '--model-embeddings',
        default='voyage'
    )
    args = parser.parse_args()
    
    use_cache = not args.force_recompute
    
    if args.force_recompute:
        print("⚠️  Mode --force-recompute : le cache sera ignoré")
    
    print("📂 Lecture JSON...")
    exps  = load_json(FILES["experiences"])
    forms = load_json(FILES["formations"])
    g_sk  = load_json(FILES["skills"])
    infos = load_json(FILES["informations"])

    if not any([exps, forms, g_sk]):
        print("✗ Aucune donnée trouvée")
        return

    # vo = VoyageClient(api_key=VOYAGE_API_KEY)
    modelEmbeddings = "voyage"
    modelEmbeddings = "mistral"
    modelEmbeddings = args.model_embeddings

    # Skills uniques
    all_skills = collect_unique_skills(exps, forms, g_sk)
    print(f"✓ {len(all_skills)} compétences uniques")

    # Textes → embeddings
    info_texts = [text_information(i) for i in infos]
    exp_texts  = [text_experience(e)  for e in exps]
    form_texts = [text_formation(f)   for f in forms]

    proj_list  = [(i, p) for i,e in enumerate(exps) for p in e.get("projects",[])]
    proj_texts = [text_project(p) for _,p in proj_list]

    print(f"🔢 Embeddings à calculer : exp={len(exp_texts)} | proj={len(proj_texts)} | form={len(form_texts)}")

    info_embs  = get_embeddings(info_texts,  modelEmbeddings, use_cache)
    exp_embs  = get_embeddings(exp_texts,  modelEmbeddings, use_cache)
    proj_embs = get_embeddings(proj_texts, modelEmbeddings, use_cache)
    form_embs = get_embeddings(form_texts, modelEmbeddings, use_cache)
    # exp_embs  = []
    # proj_embs = []
    # form_embs = []

    # Génération SQL
    sql_content = generate_sql_file(infos, exps, forms, all_skills, info_embs, exp_embs, proj_embs, form_embs, proj_list)
    
    # Exécution directe
    execute_sql(sql_content)


if __name__ == "__main__":
    main()