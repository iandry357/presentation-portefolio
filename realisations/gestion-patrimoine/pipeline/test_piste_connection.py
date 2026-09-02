"""
test_piste_connection.py

Script de test ISOLE (pas un composant du pipeline final) pour valider :
    1. L'authentification OAuth2 sur PISTE
    2. Un appel /search sur le CGI avec un seul mot-clé (diagnostic — on sait
       maintenant que ça ne suffit pas pour une collecte exhaustive)
    3. Un appel /consult/getArticle sur un article connu
    4. Un appel /consult/code/tableMatieres — NOUVEAU, c'est le mécanisme
       retenu pour la collecte finale (table des matières structurée du CGI)

Usage :
    python test_piste_connection.py

Nécessite un fichier .env à côté de ce script avec :
    PISTE_ENV=sandbox            # ou "production"
    PISTE_CLIENT_ID=...
    PISTE_CLIENT_SECRET=...
"""

import json
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

PISTE_ENV = os.getenv("PISTE_ENV", "sandbox").lower()
CLIENT_ID = os.getenv("PISTE_CLIENT_ID")
CLIENT_SECRET = os.getenv("PISTE_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    raise ValueError("PISTE_CLIENT_ID et PISTE_CLIENT_SECRET doivent être définis dans .env")

if PISTE_ENV == "production":
    TOKEN_URL = "https://oauth.piste.gouv.fr/api/oauth/token"
    BASE_URL = "https://api.piste.gouv.fr"
else:
    TOKEN_URL = "https://sandbox-oauth.piste.gouv.fr/api/oauth/token"
    BASE_URL = "https://sandbox-api.piste.gouv.fr"

API_URL = f"{BASE_URL}/dila/legifrance/lf-engine-app"

CODE_CIBLE = "Code général des impôts"
CODE_TEXT_ID = "LEGITEXT000006069577"  # id du CGI, confirmé via le champ "cid" du /search précédent
CODE_FACETTE_NAME = "NOM_CODE"
MOT_CLE_TEST = "donation"


def afficher_titre(titre: str):
    print("\n" + "=" * 70)
    print(titre)
    print("=" * 70)


def get_access_token() -> str:
    afficher_titre("ETAPE 1 — Authentification OAuth2")
    response = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scope": "openid",
        },
        timeout=30,
    )
    print(f"Status code : {response.status_code}")
    response.raise_for_status()
    token_data = response.json()
    print(f"Token obtenu, expire dans {token_data.get('expires_in')}s")
    return token_data["access_token"]


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def tester_table_matieres(token: str) -> dict:
    afficher_titre(f"ETAPE 4 — POST /consult/code/tableMatieres (textId={CODE_TEXT_ID})")

    payload = {
        "date": int(time.time() * 1000),  # maintenant, en millisecondes
        "sctId": "",  # vide = racine du code entier
        "textId": CODE_TEXT_ID,
    }

    print("Payload envoyé :")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    response = requests.post(
        f"{API_URL}/consult/code/tableMatieres",
        headers=_headers(token),
        json=payload,
        timeout=30,
    )
    print(f"\nStatus code : {response.status_code}")

    if response.status_code != 200:
        print("Réponse brute (erreur) :")
        print(response.text)
        response.raise_for_status()

    resultat = response.json()

    # La réponse peut être volumineuse (tout le CGI) — on tronque l'affichage
    # si c'est trop long, mais on garde tout dans le fichier de sortie pour
    # inspection complète.
    dump = json.dumps(resultat, ensure_ascii=False, indent=2)
    print("\nRéponse brute (tronquée à 5000 caractères si plus long) :")
    print(dump[:5000])
    if len(dump) > 5000:
        print(f"... [{len(dump) - 5000} caractères supplémentaires, voir table_matieres_output.json]")

    os.makedirs("data", exist_ok=True)
    with open("data/table_matieres_output.json", "w", encoding="utf-8") as f:
        f.write(dump)

    return resultat


def main():
    token = get_access_token()
    tester_table_matieres(token)

    afficher_titre("RESUME")
    print(
        "Réponse complète écrite dans data/table_matieres_output.json — "
        "regarde la structure (clés des noeuds, comment les articles sont "
        "nichés) pour qu'on prépare le parsing dans legifrance_collector.py."
    )


if __name__ == "__main__":
    main()