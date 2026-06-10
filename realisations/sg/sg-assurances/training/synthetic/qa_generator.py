"""
QA Generator — Paires instruction/input/output pour fine-tuning QLoRA
Source : 284 chunks PDF réels SG depuis ChromaDB OVH
Modèle : Mistral via Ollama local
Format sortie : Alpaca JSONL — data/qa_pairs/qa_pairs.jsonl
"""

import json
import sys
import os
import time
from pathlib import Path
from dotenv import load_dotenv
import requests
import chromadb
from chromadb.config import Settings

# ─────────────────────────────────────────
# Env + paths
# ─────────────────────────────────────────
load_dotenv(Path(__file__).parent.parent / ".env")

DATA_DIR   = Path(__file__).parent.parent / "data"
QA_DIR     = DATA_DIR / "qa_pairs"
QA_FILE    = QA_DIR / "qa_pairs.jsonl"
QA_DIR.mkdir(parents=True, exist_ok=True)

CHROMA_HOST       = os.getenv("CHROMA_HOST", "51.68.130.23")
CHROMA_PORT       = int(os.getenv("CHROMA_PORT", "8000"))
CHROMA_USERNAME   = os.getenv("CHROMA_USERNAME", "")
CHROMA_PASSWORD   = os.getenv("CHROMA_PASSWORD", "")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION_SG", "sg_assurances_news")

OLLAMA_URL        = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL      = os.getenv("OLLAMA_MODEL", "mistral")

# ─────────────────────────────────────────
# Paramètres
# ─────────────────────────────────────────
MIN_CHUNK_LEN    = 100    # chars — chunks trop courts écartés
MIN_OUTPUT_LEN   = 30     # chars — réponse trop courte = rejet
MAX_OUTPUT_LEN   = 800    # chars — réponse trop longue = rejet
OLLAMA_TIMEOUT   = 120    # secondes par appel
SLEEP_BETWEEN    = 0.5    # secondes entre appels Ollama


# ─────────────────────────────────────────
# ChromaDB — collecte chunks
# ─────────────────────────────────────────
def _get_chroma_client() -> chromadb.HttpClient:
    return chromadb.HttpClient(
        host=CHROMA_HOST,
        port=CHROMA_PORT,
        settings=Settings(
            chroma_client_auth_provider="chromadb.auth.basic_authn.BasicAuthClientProvider",
            chroma_client_auth_credentials=f"{CHROMA_USERNAME}:{CHROMA_PASSWORD}",
        ),
    )


def collect_chunks() -> list[dict]:
    """
    Récupère tous les chunks PDF depuis ChromaDB OVH.
    Filtre sur source=pdf et longueur minimale.
    Retourne liste de dicts {id, text, metadata}.
    """
    print(f"[qa_generator] Connexion ChromaDB {CHROMA_HOST}:{CHROMA_PORT}...")
    client = _get_chroma_client()

    collection = client.get_collection(name=CHROMA_COLLECTION)
    total = collection.count()
    print(f"[qa_generator] Collection '{CHROMA_COLLECTION}' — {total} documents")

    # Récupérer tous les documents avec métadonnées
    result = collection.get(include=["documents", "metadatas"])

    chunks = []
    for doc_id, text, meta in zip(result["ids"], result["documents"], result["metadatas"]):
        # Filtrer sur source PDF uniquement
        if meta.get("source") != "pdf":
            continue
        # Filtrer chunks trop courts
        if not text or len(text.strip()) < MIN_CHUNK_LEN:
            continue
        chunks.append({
            "id": doc_id,
            "text": text.strip(),
            "metadata": meta,
        })

    print(f"[qa_generator] {len(chunks)} chunks PDF retenus après filtrage")
    return chunks


# ─────────────────────────────────────────
# Prompt builder
# ─────────────────────────────────────────
def _build_prompt(chunk_text: str) -> str:
    return f"""Tu es un expert en assurance. À partir du passage suivant extrait d'un document SG Assurances, génère une paire question/réponse en français.

Passage :
\"\"\"
{chunk_text}
\"\"\"

Réponds UNIQUEMENT avec un objet JSON valide, sans texte avant ni après, sans balises markdown, exactement dans ce format :
{{
  "instruction": "une question précise sur le contenu du passage",
  "input": "",
  "output": "une réponse complète et factuelle basée uniquement sur le passage"
}}"""


# ─────────────────────────────────────────
# Ollama — génération
# ─────────────────────────────────────────
def _call_ollama(prompt: str) -> str | None:
    """
    Appel Ollama local — retourne le texte brut de la réponse ou None si échec.
    """
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 400,
                },
            },
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except requests.exceptions.Timeout:
        print("  [WARN] Ollama timeout")
        return None
    except Exception as e:
        print(f"  [WARN] Ollama error: {e}")
        return None


# ─────────────────────────────────────────
# Parsing + validation JSON Alpaca
# ─────────────────────────────────────────
def _parse_and_validate(raw: str) -> dict | None:
    """
    Parse la réponse Ollama et valide le format Alpaca.
    Retourne le dict validé ou None si invalide.
    """
    if not raw:
        return None

    # Nettoyer les balises markdown éventuelles
    clean = raw.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        # Retirer première et dernière ligne si ce sont des balises
        lines = [l for l in lines if not l.strip().startswith("```")]
        clean = "\n".join(lines).strip()

    # Parser JSON
    try:
        data = json.loads(clean)
    except json.JSONDecodeError:
        # Tentative de récupération : chercher le premier { ... }
        start = clean.find("{")
        end   = clean.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        try:
            data = json.loads(clean[start:end])
        except json.JSONDecodeError:
            return None

    # Vérifier les 3 clés Alpaca
    if not all(k in data for k in ("instruction", "input", "output")):
        return None

    instruction = str(data["instruction"]).strip()
    output      = str(data["output"]).strip()

    # Valider longueurs
    if len(instruction) < 10:
        return None
    if len(output) < MIN_OUTPUT_LEN:
        return None
    if len(output) > MAX_OUTPUT_LEN:
        return None

    # Vérifier que la réponse n'est pas un refus ou placeholder
    refus_patterns = [
        "je ne sais pas",
        "je n'ai pas",
        "aucune information",
        "passage ne mentionne",
        "not mentioned",
        "cannot answer",
    ]
    output_lower = output.lower()
    if any(p in output_lower for p in refus_patterns):
        return None

    return {
        "instruction": instruction,
        "input": "",
        "output": output,
    }


# ─────────────────────────────────────────
# Dédoublonnage
# ─────────────────────────────────────────
def _load_existing_instructions(path: Path) -> set[str]:
    """Charge les instructions déjà écrites pour éviter les doublons."""
    seen = set()
    if not path.exists():
        return seen
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
                seen.add(obj["instruction"].strip().lower())
            except Exception:
                continue
    return seen


# ─────────────────────────────────────────
# Pipeline principal
# ─────────────────────────────────────────
def generate_qa_pairs() -> int:
    """
    Pipeline complet : collecte → génération → filtrage → écriture.
    Retourne le nombre de paires écrites.
    """
    # Nettoyage au démarrage
    if QA_FILE.exists():
        QA_FILE.unlink()
        print(f"[qa_generator] Nettoyage {QA_FILE.name}")

    # Collecte chunks
    chunks = collect_chunks()
    if not chunks:
        print("[qa_generator] Aucun chunk disponible — arrêt")
        return 0

    seen_instructions = _load_existing_instructions(QA_FILE)
    written  = 0
    rejected = 0
    total    = len(chunks)

    print(f"[qa_generator] Génération QA sur {total} chunks via Ollama ({OLLAMA_MODEL})...")

    with open(QA_FILE, "a", encoding="utf-8") as out:
        for i, chunk in enumerate(chunks):
            prompt = _build_prompt(chunk["text"])
            raw    = _call_ollama(prompt)
            pair   = _parse_and_validate(raw)

            if pair is None:
                rejected += 1
                if (i + 1) % 20 == 0 or (i + 1) == total:
                    print(f"  [{i+1}/{total}] écrit={written} rejeté={rejected}")
                time.sleep(SLEEP_BETWEEN)
                continue

            # Dédoublonnage sur instruction
            key = pair["instruction"].lower()
            if key in seen_instructions:
                rejected += 1
                time.sleep(SLEEP_BETWEEN)
                continue

            seen_instructions.add(key)
            out.write(json.dumps(pair, ensure_ascii=False) + "\n")
            out.flush()
            written += 1

            if (i + 1) % 20 == 0 or (i + 1) == total:
                print(f"  [{i+1}/{total}] écrit={written} rejeté={rejected}")

            time.sleep(SLEEP_BETWEEN)

    print(f"\n[qa_generator] Terminé — {written} paires écrites → {QA_FILE}")
    return written


# ─────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────
if __name__ == "__main__":
    total = generate_qa_pairs()
    if total == 0:
        print("[qa_generator] Aucune paire générée — vérifier ChromaDB et Ollama")
        sys.exit(1)
    print(f"[qa_generator] Done — {total} paires QA disponibles dans {QA_FILE}")