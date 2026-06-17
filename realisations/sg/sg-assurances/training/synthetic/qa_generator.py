"""
QA Generator — Paires instruction/input/output pour fine-tuning QLoRA
Sources :
  1. ChromaDB OVH      — 570 chunks PDF réels SG
  2. zelros/insurance-fr — 201 paires MRH françaises (HuggingFace)
  3. code-assurances   — articles Code des assurances FR (HuggingFace)
Modèle : Mistral via Ollama local (sources 1 et 3)
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
from datasets import load_dataset

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
MIN_CHUNK_LEN    = 100
MIN_OUTPUT_LEN   = 30
MAX_OUTPUT_LEN   = 800
OLLAMA_TIMEOUT   = 120
SLEEP_BETWEEN    = 0.5

# Mots clés pour filtrer les articles code-assurances pertinents
CODE_ASSURANCES_KEYWORDS = [
    "habitation", "automobile", "auto", "sinistre", "garantie",
    "prescription", "résiliation", "indemnisation", "assurée",
    "assuré", "contrat", "prime", "franchise", "dommage",
    "responsabilité", "déclaration", "couverture", "échéance",
]


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
    print(f"[ChromaDB] Connexion {CHROMA_HOST}:{CHROMA_PORT}...")
    client     = _get_chroma_client()
    collection = client.get_collection(name=CHROMA_COLLECTION)
    total      = collection.count()
    print(f"[ChromaDB] Collection '{CHROMA_COLLECTION}' — {total} documents")

    result = collection.get(include=["documents", "metadatas"])
    chunks = []
    for doc_id, text, meta in zip(result["ids"], result["documents"], result["metadatas"]):
        if meta.get("source") != "pdf":
            continue
        if not text or len(text.strip()) < MIN_CHUNK_LEN:
            continue
        chunks.append({"id": doc_id, "text": text.strip(), "metadata": meta})

    print(f"[ChromaDB] {len(chunks)} chunks PDF retenus")
    return chunks


# ─────────────────────────────────────────
# Source 2 — zelros/insurance-fr
# ─────────────────────────────────────────
def collect_zelros() -> list[dict]:
    print("\n[Zelros] Chargement zelros/insurance-fr...")
    ds     = load_dataset("zelros/insurance-fr", split="train")
    pairs  = []
    for row in ds:
        instruction = str(row.get("title", "")).strip()
        output      = str(row.get("content", "")).strip()

        if len(instruction) < 10:
            continue
        if len(output) < MIN_OUTPUT_LEN:
            continue
        if len(output) > MAX_OUTPUT_LEN:
            output = output[:MAX_OUTPUT_LEN].rsplit(".", 1)[0] + "."

        pairs.append({
            "instruction": instruction,
            "input": "",
            "output": output,
        })

    print(f"[Zelros] {len(pairs)} paires retenues")
    return pairs


# ─────────────────────────────────────────
# Source 3 — louisbrulenaudet/code-assurances
# ─────────────────────────────────────────
def collect_code_assurances() -> list[dict]:
    print("\n[Code Assurances] Chargement louisbrulenaudet/code-assurances...")
    ds = load_dataset("louisbrulenaudet/code-assurances", split="train")

    articles = []
    for row in ds:
        texte = str(row.get("texte", "")).strip()
        ref   = str(row.get("ref", "")).strip()

        if len(texte) < MIN_CHUNK_LEN:
            continue

        # Filtrer sur mots clés métier
        texte_lower = texte.lower()
        if not any(kw in texte_lower for kw in CODE_ASSURANCES_KEYWORDS):
            continue

        articles.append({"text": texte, "ref": ref})

    print(f"[Code Assurances] {len(articles)} articles retenus après filtrage")
    return articles


# ─────────────────────────────────────────
# Prompt builder
# ─────────────────────────────────────────
def _build_prompt_chunk(chunk_text: str) -> str:
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


def _build_prompt_article(texte: str, ref: str) -> str:
    return f"""Tu es un expert en droit des assurances français. À partir de l'article suivant du Code des assurances ({ref}), génère une paire question/réponse en français.

Article :
\"\"\"
{texte}
\"\"\"

Réponds UNIQUEMENT avec un objet JSON valide, sans texte avant ni après, sans balises markdown, exactement dans ce format :
{{
  "instruction": "une question précise sur cet article du Code des assurances",
  "input": "",
  "output": "une réponse complète et factuelle basée uniquement sur cet article"
}}"""


# ─────────────────────────────────────────
# Ollama — génération
# ─────────────────────────────────────────
def _call_ollama(prompt: str) -> str | None:
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model":  OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 400},
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
    if not raw:
        return None

    clean = raw.strip()
    if clean.startswith("```"):
        lines = [l for l in clean.split("\n") if not l.strip().startswith("```")]
        clean = "\n".join(lines).strip()

    try:
        data = json.loads(clean)
    except json.JSONDecodeError:
        start = clean.find("{")
        end   = clean.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        try:
            data = json.loads(clean[start:end])
        except json.JSONDecodeError:
            return None

    if not all(k in data for k in ("instruction", "input", "output")):
        return None

    instruction = str(data["instruction"]).strip()
    output      = str(data["output"]).strip()

    if len(instruction) < 10:
        return None
    if len(output) < MIN_OUTPUT_LEN or len(output) > MAX_OUTPUT_LEN:
        return None

    refus_patterns = [
        "je ne sais pas", "je n'ai pas", "aucune information",
        "passage ne mentionne", "not mentioned", "cannot answer",
    ]
    if any(p in output.lower() for p in refus_patterns):
        return None

    return {"instruction": instruction, "input": "", "output": output}


# ─────────────────────────────────────────
# Dédoublonnage
# ─────────────────────────────────────────
def _load_existing_instructions(path: Path) -> set[str]:
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
# Écriture sécurisée
# ─────────────────────────────────────────
def _write_pair(f, pair: dict, seen: set[str]) -> bool:
    key = pair["instruction"].lower()
    if key in seen:
        return False
    seen.add(key)
    f.write(json.dumps(pair, ensure_ascii=False) + "\n")
    f.flush()
    return True


# ─────────────────────────────────────────
# Pipeline principal
# ─────────────────────────────────────────
def generate_qa_pairs() -> int:
    # Nettoyage
    if QA_FILE.exists():
        QA_FILE.unlink()
        print(f"[qa_generator] Nettoyage {QA_FILE.name}")

    seen     = set()
    written  = 0

    with open(QA_FILE, "a", encoding="utf-8") as out:

        # ── Source 2 : Zelros (direct, pas d'Ollama) ──────────────────
        print("\n" + "="*50)
        print("SOURCE 2 — zelros/insurance-fr")
        print("="*50)
        zelros_pairs = collect_zelros()
        zelros_written = 0
        for pair in zelros_pairs:
            if _write_pair(out, pair, seen):
                zelros_written += 1
                written += 1
        print(f"[Zelros] {zelros_written} paires écrites")

        # ── Source 1 : ChromaDB (Ollama) ───────────────────────────────
        print("\n" + "="*50)
        print("SOURCE 1 — ChromaDB OVH (PDFs SG)")
        print("="*50)
        chunks         = collect_chunks()
        chroma_written = 0
        chroma_rejected = 0
        total_chroma   = len(chunks)

        for i, chunk in enumerate(chunks):
            prompt = _build_prompt_chunk(chunk["text"])
            raw    = _call_ollama(prompt)
            pair   = _parse_and_validate(raw)

            if pair and _write_pair(out, pair, seen):
                chroma_written += 1
                written += 1
            else:
                chroma_rejected += 1

            if (i + 1) % 20 == 0 or (i + 1) == total_chroma:
                print(f"  [{i+1}/{total_chroma}] écrit={chroma_written} rejeté={chroma_rejected}")

            time.sleep(SLEEP_BETWEEN)

        print(f"[ChromaDB] {chroma_written} paires écrites")

        # ── Source 3 : Code des assurances (Ollama) ───────────────────
        # print("\n" + "="*50)
        # print("SOURCE 3 — Code des assurances (louisbrulenaudet)")
        # print("="*50)
        # articles       = collect_code_assurances()
        # code_written   = 0
        # code_rejected  = 0
        # total_code     = len(articles)

        # for i, article in enumerate(articles):
        #     prompt = _build_prompt_article(article["text"], article["ref"])
        #     raw    = _call_ollama(prompt)
        #     pair   = _parse_and_validate(raw)

        #     if pair and _write_pair(out, pair, seen):
        #         code_written += 1
        #         written += 1
        #     else:
        #         code_rejected += 1

        #     if (i + 1) % 20 == 0 or (i + 1) == total_code:
        #         print(f"  [{i+1}/{total_code}] écrit={code_written} rejeté={code_rejected}")

        #     time.sleep(SLEEP_BETWEEN)

        # print(f"[Code Assurances] {code_written} paires écrites")

    print(f"\n[qa_generator] Terminé — {written} paires totales → {QA_FILE}")
    print(f"  Zelros       : {zelros_written}")
    print(f"  ChromaDB     : {chroma_written}")
    # print(f"  Code Assur.  : {code_written}")
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