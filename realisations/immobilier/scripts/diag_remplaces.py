"""Diagnostic : où est l'ancien DPE d'un DPE remplaçant ? Lecture seule."""
import requests

# ── Paramètres ──────────────────────────────────────────────
DPE_API = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant"
QS_REMPLACANTS = "code_departement_ban:75 AND _exists_:numero_dpe_remplace"
NB_EXEMPLES = 5
MOTS_CLES_CHAMPS = ("statut", "valid", "remplac", "ancien", "version", "modele", "invalid")
TIMEOUT = 60


def get(url, **params):
    r = requests.get(url, params=params, timeout=TIMEOUT)
    return r.status_code, (r.json() if r.ok else r.text[:200])


def chercher(numero, methode):
    """Cherche un numero_dpe par une des 3 méthodes ; renvoie (statut HTTP, trouvé ?, nb de lignes renvoyées)."""
    params = {"size": 5, "select": "numero_dpe,etiquette_dpe,date_etablissement_dpe"}
    if methode == "qs":
        params["qs"] = f'numero_dpe:"{numero}"'
    elif methode == "eq":
        params["numero_dpe_eq"] = numero
    else:
        params["numero_dpe_in"] = numero
    statut, data = get(f"{DPE_API}/lines", **params)
    if statut != 200:
        return statut, False, data
    lignes = data["results"]
    return statut, any(l["numero_dpe"] == numero for l in lignes), len(lignes)


def main():
    statut, schema = get(f"{DPE_API}/schema")
    print("== Champs liés au statut / à la version ==")
    if statut == 200:
        for champ in schema:
            if any(m in champ["key"].lower() for m in MOTS_CLES_CHAMPS):
                print(f"  {champ['key']}")
    else:
        print(f"  schema : HTTP {statut} {schema}")

    statut, data = get(
        f"{DPE_API}/lines",
        qs=QS_REMPLACANTS,
        size=NB_EXEMPLES,
        sort="_rand",
        select="numero_dpe,numero_dpe_remplace,date_etablissement_dpe,etiquette_dpe,version_dpe,modele_dpe",
    )
    if statut != 200:
        print(f"ERREUR HTTP {statut} : {data}")
        return

    for ligne in data["results"]:
        print(f"\n--- {ligne}")
        # Témoin : le DPE remplaçant existe forcément dans le jeu.
        # Si une méthode ne le retrouve pas, c'est le filtre qui est en cause.
        for cible, libelle in ((ligne["numero_dpe"], "TEMOIN (le DPE lui-même)"),
                               (ligne["numero_dpe_remplace"], "ANCIEN (numero_dpe_remplace)")):
            print(f"  {libelle} : {cible}")
            for methode in ("qs", "eq", "in"):
                http, trouve, nb = chercher(cible, methode)
                print(f"    {methode:>2} : HTTP {http}, trouvé={trouve}, lignes renvoyées={nb}")


if __name__ == "__main__":
    main()
