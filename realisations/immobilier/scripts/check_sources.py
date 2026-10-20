"""Mesure des sources DPE (ADEME) et DVF (Etalab) pour Paris. Lecture seule."""
import sys
from collections import Counter

import requests

# ── Paramètres ──────────────────────────────────────────────
DPE_API = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant"
DPE_DEPARTEMENT = "75"
DVF_URL = "https://files.data.gouv.fr/geo-dvf/latest/csv/{annee}/departements/75.csv.gz"
DVF_ANNEES = range(2020, 2027)
TAILLE_ECHANTILLON = 2000
TAILLE_LOT_IN = 100
TIMEOUT = 60
ETIQUETTES = ["A", "B", "C", "D", "E", "F", "G"]
DATE_REFORME = "2026-01-01"

QS_PARIS = f"code_departement_ban:{DPE_DEPARTEMENT}"


def get(url, **params):
    r = requests.get(url, params=params, timeout=TIMEOUT)
    if not r.ok:
        print(f"ERREUR HTTP {r.status_code} sur {r.url}\n{r.text[:300]}")
        sys.exit(1)
    return r.json()


def total(qs):
    return get(f"{DPE_API}/lines", qs=qs, size=1, select="numero_dpe")["total"]


def repartition(champ, qs):
    data = get(f"{DPE_API}/values_agg", field=champ, qs=qs, agg_size=20)
    return {a["value"]: a["total"] for a in data["aggs"]}


def echantillon():
    data = get(
        f"{DPE_API}/lines",
        qs=f"{QS_PARIS} AND _exists_:numero_dpe_remplace",
        size=TAILLE_ECHANTILLON,
        sort="_rand",
        select="numero_dpe,numero_dpe_remplace,etiquette_dpe,date_etablissement_dpe,type_energie_principale_chauffage",
    )
    return data["total"], data["results"]


def anciens(numeros):
    """Étiquette des DPE remplacés qui sont présents dans le jeu parisien."""
    trouves = {}
    for i in range(0, len(numeros), TAILLE_LOT_IN):
        lot = numeros[i:i + TAILLE_LOT_IN]
        data = get(
            f"{DPE_API}/lines",
            qs=QS_PARIS,
            numero_dpe_in=",".join(lot),
            size=len(lot),
            select="numero_dpe,etiquette_dpe",
        )
        for ligne in data["results"]:
            trouves[ligne["numero_dpe"]] = ligne["etiquette_dpe"]
    return trouves


def pct(a, b):
    return f"{100 * a / b:.1f} %" if b else "n/a"


def check_dpe():
    print("== DPE (ADEME dpe03existant, Paris) ==")
    n_paris = total(QS_PARIS)
    print(f"Total DPE : {n_paris}")
    print(f"Par étiquette : {repartition('etiquette_dpe', QS_PARIS)}")
    print(f"Par énergie de chauffage : {repartition('type_energie_principale_chauffage', QS_PARIS)}")

    n_remplace, lignes = echantillon()
    print(f"\nDPE avec numero_dpe_remplace : {n_remplace} ({pct(n_remplace, n_paris)} du parc)")
    print(f"Échantillon aléatoire : {len(lignes)} DPE remplaçants")

    remplaces = sorted({l["numero_dpe_remplace"] for l in lignes})
    avant = anciens(remplaces)
    rapproches = [l for l in lignes if l["numero_dpe_remplace"] in avant]
    print(f"Ancien DPE présent dans le jeu : {len(rapproches)} / {len(lignes)} ({pct(len(rapproches), len(lignes))})")

    transitions = Counter()
    ecarts = Counter()
    recalcul, travaux = 0, 0
    for l in rapproches:
        av, ap = avant[l["numero_dpe_remplace"]], l["etiquette_dpe"]
        if av not in ETIQUETTES or ap not in ETIQUETTES:
            continue
        ecart = ETIQUETTES.index(av) - ETIQUETTES.index(ap)
        transitions[(av, ap)] += 1
        ecarts[ecart] += 1
        if ecart > 0:
            electrique = "lectric" in (l.get("type_energie_principale_chauffage") or "").lower()
            post_reforme = (l.get("date_etablissement_dpe") or "")[:10] >= DATE_REFORME
            if electrique and post_reforme:
                recalcul += 1
            else:
                travaux += 1

    print(f"Écarts de classes (positif = amélioration) : {dict(sorted(ecarts.items()))}")
    print(f"Transitions les plus fréquentes : {transitions.most_common(10)}")
    print(f"Améliorations 'probablement recalcul 2026' : {recalcul} ; 'probablement travaux' : {travaux}")


def check_dvf():
    print("\n== DVF (Etalab, Paris 75) ==")
    for annee in DVF_ANNEES:
        r = requests.head(DVF_URL.format(annee=annee), allow_redirects=True, timeout=TIMEOUT)
        taille = r.headers.get("Content-Length")
        detail = f", {int(taille) / 1e6:.1f} Mo" if taille else ""
        print(f"  {annee} : HTTP {r.status_code}{detail}")


if __name__ == "__main__":
    check_dpe()
    check_dvf()
