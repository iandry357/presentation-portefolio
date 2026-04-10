"""
Script one-shot — Exploration codes ROME via ROMEO v2.

Objectif :
  1. Récupérer les codes ROME directs pour une liste d'intitulés cibles
  2. Récupérer les codes ROME voisins pour chaque code direct
  3. Afficher la liste finale dédupliquée pour validation manuelle

Usage :
  python explore_rome_codes.py

Variables d'environnement requises :
  FT_CLIENT_ID
  FT_CLIENT_SECRET
"""

import os
import sys
import httpx
import time
import json
import asyncio
from google.cloud import storage as gcs

# ============================================================================
# Config
# ============================================================================

FT_CLIENT_ID     = os.environ.get("FT_CLIENT_ID", "").strip()
FT_CLIENT_SECRET = os.environ.get("FT_CLIENT_SECRET", "").strip()
# GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
GCS_BUCKET = os.environ.get("GCS_BUCKET", "portfolio-emploi-config")
GCS_ROME_FILE = "rome_codes_direct.json"


if not FT_CLIENT_ID or not FT_CLIENT_SECRET:
    print("❌ FRANCE_TRAVAIL_CLIENT_ID et FRANCE_TRAVAIL_CLIENT_SECRET requis en variables d'environnement")
    sys.exit(1)

# Intitulés cibles à explorer
# ROLE_TARGETS = [
#     "Data Scientist",
#     "Machine Learning Engineer",
#     "Data engineer",
#     "MLOps Engineer",
#     "AI Engineer",
#     "Ingénieur en Machine Learning",
#     "Ingénieur de données",
# ]

ROLE_TARGETS = [
    # Cœur métier data/ML
    "Data Scientist",
    "Data Scientist Python",
    "Data Scientist NLP",
    "Machine Learning Engineer",
    "Ingénieur Machine Learning",
    "Data Engineer",
    "Ingénieur de données",
    "Ingénieur données Python Spark",
    "MLOps Engineer",
    "Ingénieur MLOps Kubernetes",
    "AI Engineer",
    "Ingénieur Intelligence Artificielle",    
    # Spatial & OLAP
    "Ingénieur OLAP",
    "Ingénieur décisionnel OLAP",
    "Ingénieur Spatial OLAP",
    "Ingénieur SIG données",
    "Ingénieur géospatial",
    "Spatial Data Engineer",
    "GIS Data Engineer",
    # Analytics & BI
    "Data Analyst",
    "Analyste données SQL",
    "Business Intelligence Engineer",
    "Ingénieur BI",
    "Analyste décisionnel",
    # Spécialisations
    "Ingénieur NLP",
    "Ingénieur deep learning",
    "Computer Vision Engineer",
    "Ingénieur vision par ordinateur",
    "Ingénieur modélisation statistique",
    # Infra & Cloud data
    "Ingénieur Cloud AWS data",
    "Ingénieur Cloud GCP",
    "Architecte données",
    "Architecte base de données",
    "Ingénieur Big Data Spark Hadoop",
    # Dev & Backend orienté data
    "Développeur Python Machine Learning",
    "Développeur Python FastAPI",
    "Ingénieur backend Python",
    # LLM & GenAI
    "Ingénieur LLM",
    "Ingénieur GenAI",
    "Ingénieur IA Générative",
    "Prompt Engineer",
    "Ingénieur RAG",
    "Développeur LLM Python",
    "AI Engineer LLM",
    "Ingénieur foundation models",
    # Orchestration & Agents
    "Ingénieur LangChain",
    "Ingénieur agents IA",
    "Ingénieur pipelines IA",
    # Anglais — Cœur métier
    "Data Scientist",
    "Machine Learning Engineer",
    "Data Engineer",
    "MLOps Engineer",
    "AI Engineer",
    "ML Engineer",
    # Anglais — Analytics
    "Data Analyst",
    "Business Intelligence Engineer",
    "BI Engineer",
    # Anglais — Spécialisations
    "NLP Engineer",
    "Deep Learning Engineer",
    "Computer Vision Engineer",
    "Research Scientist",
    "Applied Scientist",
    # Anglais — Cloud & Infra
    "Cloud Data Engineer",
    "Big Data Engineer",
    "Data Architect",
    "Database Architect",
    # Anglais — LLM & GenAI
    "LLM Engineer",
    "GenAI Engineer",
    "Prompt Engineer",
    "RAG Engineer",
    "AI Research Engineer",
    "Foundation Model Engineer",
    # Anglais — Agents & Orchestration
    "AI Agent Engineer",
    "LangChain Engineer",
    "AI Pipeline Engineer",
    # Systèmes d'information & Aide à la décision
    "Responsable système d'information décisionnel",
    "Chef de projet Business Intelligence",
    "Chef de projet décisionnel",
    "Consultant en système d'information",
    "Ingénieur système d'information",
    "Maître d'ouvrage SI décisionnel",
    "Product Owner data",
    "Product Manager data",
    "Responsable données",
    "Chief Data Officer",
    "Data Manager",
    "Data Steward",
    "Data Governance",
    "Ingénieur ETL",
    "Développeur ETL",
    "Ingénieur intégration données",
    "Ingénieur datawarehouse",
    "Data Warehouse Engineer",
    "ETL Developer",
    "BI Developer",
]

# Seuil de confiance minimum pour retenir un code ROME (0.0 à 1.0)
SCORE_MIN = 0.5

# Nombre max de voisins à récupérer par code direct
MAX_NEIGHBORS = 5

# ============================================================================
# Auth France Travail
# ============================================================================

def get_ft_token() -> str:
    resp = httpx.post(
        "https://entreprise.francetravail.fr/connexion/oauth2/access_token",
        params={"realm": "/partenaire"},
        data={
            "grant_type":    "client_credentials",
            "client_id":     FT_CLIENT_ID,
            "client_secret": FT_CLIENT_SECRET,
            "scope":         "api_romeov2",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]

# ============================================================================
# ROMEO v2
# ============================================================================

def predict_rome(token: str, intitule: str) -> list[dict]:
    """
    Retourne les codes ROME prédits pour un intitulé de poste.
    Chaque entrée : { code, libelle, score }
    """
    resp = httpx.post(
        "https://api.francetravail.io/partenaire/romeo/v2/predictionMetiers",
        headers={"Authorization": f"Bearer {token}"},
        # json={"intitulePoste": intitule, "nombreResultats": 5},
        json={
            "appellations": [
                {
                    "intitule":    intitule,
                    "identifiant": "exploration-rome",
                }
            ],
            "options": {
                "nomAppelant":          "portfolio-emploi",
                "nbResultats":          10,
                "seuilScorePrediction": SCORE_MIN,
            },
        },
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"  ⚠️  ROMEO erreur {resp.status_code} pour '{intitule}'")
        return []

    results = []
    for prediction in resp.json():
        for metier in prediction.get("metiersRome", []):
            code    = metier.get("codeRome", "")
            libelle = metier.get("libelleRome", "")
            score   = metier.get("scorePrediction", 0.0)
            if code:
                results.append({"code": code, "libelle": libelle, "score": round(score, 3)})

    time.sleep(0.4)
    return results


def get_rome_neighbors(token: str, code_rome: str) -> list[dict]:
    """
    Retourne les codes ROME voisins d'un code donné.
    Chaque entrée : { code, libelle }
    """
    resp = httpx.get(
        f"https://api.francetravail.io/partenaire/romeo/v2/metier/{code_rome}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"  ⚠️  Voisins erreur {resp.status_code} pour '{code_rome}'")
        return []

    data     = resp.json()
    voisins  = data.get("metiersProches", [])[:MAX_NEIGHBORS]
    results  = []
    for v in voisins:
        code    = v.get("codeRome", "")
        libelle = v.get("libelleRome", "")
        if code:
            results.append({"code": code, "libelle": libelle})
    time.sleep(0.4)
    return results

def validate_rome_with_llm(codes: dict[str, dict]) -> dict[str, dict]:
    """
    Valide chaque code ROME via Groq/Llama.
    Enrichit chaque entrée avec metier_OK et justification.
    """
    if not OPENAI_API_KEY:
        print("  ⚠️  OPENAI_API_KEY absent — validation LLM ignorée")
        for code in codes:
            codes[code]["metier_OK"] = True
            codes[code]["justification"] = "Non validé — OPENAI_API_KEY absent"
        return codes

    for code, info in codes.items():
        prompt = f"""Tu es un expert en classification des métiers du numérique.

Code ROME : {code}
Libellé : {info['libelle']}

Ce métier est-il directement orienté data, base de donnée, entrepôt de donnée, analyse spatiale, developpement web, machine learning, MLOps, intelligence artificielle, analytics ou système d'information ou aide à la décision ?

Réponds UNIQUEMENT en JSON avec ce format exact :
{{"metier_OK": true, "justification": "raison courte"}}
ou
{{"metier_OK": false, "justification": "raison courte"}}"""

        try:
            resp = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 100,
                },
                timeout=15,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            content = content.replace("```json", "").replace("```", "").strip()
            result = json.loads(content)
            codes[code]["metier_OK"]     = result.get("metier_OK", True)
            codes[code]["justification"] = result.get("justification", "")
            status = "✅" if codes[code]["metier_OK"] else "❌"
            print(f"  {status} {code} — {info['libelle']} : {codes[code]['justification']}")
        except Exception as e:
            print(f"  ⚠️  Erreur Groq pour {code} : {e}")
            codes[code]["metier_OK"]     = True
            codes[code]["justification"] = f"Erreur validation : {e}"

        time.sleep(0.2)

    return codes


# ============================================================================
# Main
# ============================================================================

def main() -> None:
    print("=" * 60)
    print("Exploration codes ROME — ROMEO v2")
    print("=" * 60)

    token = get_ft_token()
    print(f"✅ Token France Travail obtenu\n")

    direct_codes: dict[str, dict] = {}    # code → { libelle, score, source_intitule }
    neighbor_codes: dict[str, dict] = {}  # code → { libelle, from_code }

    # --- Étape 1 : codes directs ---
    
    print("📌 Étape 1 — Codes ROME directs\n")
    for intitule in ROLE_TARGETS:
        print(f"  🔍 '{intitule}'")
        results = predict_rome(token, intitule)
        for r in results:
            if r["code"] not in direct_codes and float(r["score"]) >= 0.50 and r["code"].startswith("M"):
                direct_codes[r["code"]] = {
                    "libelle": r["libelle"],
                    "score":   r["score"],
                    "source":  intitule,
                }
                # code_intitules[r["code"]] = {
                #     "libelle": r["libelle"],
                #     "score":   r["score"],
                #     "source":  intitule,
                # }
                print(f"      → {r['code']} — {r['libelle']} (score: {r['score']})")
        if not results:
            print(f"      → aucun résultat au-dessus du seuil {SCORE_MIN}")
    print()
    
    with open("rome_codes_direct.json", "w", encoding="utf-8") as f:
        json.dump(direct_codes, f, ensure_ascii=False, indent=2)
    print(f"\n💾 direct_codes sauvegardé dans rome_codes_direct.json")

    # # --- Étape 2 : codes voisins ---
    # print("📌 Étape 2 — Codes ROME voisins\n")
    # for code, info in direct_codes.items():
    #     print(f"  🔍 Voisins de {code} — {info['libelle']}")
    #     neighbors = get_rome_neighbors(token, code)
    #     for n in neighbors:
    #         if n["code"] not in direct_codes and n["code"] not in neighbor_codes:
    #             neighbor_codes[n["code"]] = {
    #                 "libelle":   n["libelle"],
    #                 "from_code": code,
    #             }
    #             print(f"      → {n['code']} — {n['libelle']}")
    #     if not neighbors:
    #         print(f"      → aucun voisin trouvé")
    # print()

    # --- Étape 3 : validation Groq ---
    print("📌 Étape 3 — Validation openai gpt \n")
    direct_codes = validate_rome_with_llm(direct_codes)

    # --- Sauvegarde JSON ---
    # output_path = os.path.join(os.path.dirname(__file__), "rome_codes_direct.json")
    # with open(output_path, "w", encoding="utf-8") as f:
    #     json.dump(direct_codes, f, ensure_ascii=False, indent=2)
    # print(f"\n💾 rome_codes_direct.json sauvegardé ({len(direct_codes)} codes)")

    # Sauvegarde vers Cloud Storage
    output = json.dumps(direct_codes, ensure_ascii=False, indent=2)
    gcs_client = gcs.Client()
    bucket = gcs_client.bucket(GCS_BUCKET)
    blob = bucket.blob(GCS_ROME_FILE)
    blob.upload_from_string(output, content_type="application/json")
    print(f"\n💾 rome_codes_direct.json sauvegardé dans gs://{GCS_BUCKET}/{GCS_ROME_FILE}")

    # --- Synthèse — uniquement codes validés ---
    codes_valides = {k: v for k, v in direct_codes.items() if v.get("metier_OK", True)}
    codes_ecartes = {k: v for k, v in direct_codes.items() if not v.get("metier_OK", True)}

    print()
    print("=" * 60)
    print(f"✅ Codes ROME validés — {len(codes_valides)} codes\n")
    print(f"  {'Code':<8} {'Libellé':<50} {'Score'}")
    print(f"  {'-'*8} {'-'*50} {'-'*10}")
    for code, info in codes_valides.items():
        print(f"  {code:<8} {info['libelle']:<50} {info['score']}")

    if codes_ecartes:
        print()
        print(f"❌ Codes ROME écartés — {len(codes_ecartes)} codes\n")
        for code, info in codes_ecartes.items():
            print(f"  {code:<8} {info['libelle']:<50} {info['justification']}")

    # --- Variables à copier ---
    print()
    print("📋 Variable ROME_CODES à copier :")
    print(",".join(codes_valides.keys()))

    mots_cles = [info["source"] for info in codes_valides.values()]
    mots_cles_dedup = list(dict.fromkeys(mots_cles))
    print()
    print("📋 Variable MOTS_CLES à copier :")
    print(",".join(mots_cles_dedup))
    print("=" * 60)


if __name__ == "__main__":
    main()