"""
Pivot en mémoire du cube d'analyse de l'onglet « Bâtiments (BDNB) » (tables agg_analyse_ventes et agg_analyse_dpe).
Fonctions pures : reçoivent les lignes déjà lues (voir immobilier_bdnb_bigquery.py), sans accès BigQuery ni FastAPI.
Les lignes viennent du cache : elles ne sont jamais modifiées (les listes de prix sont recopiées, pas triées sur place).
"""

NON_RENSEIGNE = "non renseigné"

# Dimensions du cube par source (rattachee n'existe que pour les ventes) et colonne d'effectif
DIMENSIONS = {
    "ventes": ["trimestre", "arrondissement", "pieces", "tranche_surface", "etiquette", "rattachee"],
    "dpe": ["trimestre", "arrondissement", "pieces", "tranche_surface", "etiquette"],
}
COMPTE = {"ventes": "nb_ventes", "dpe": "nb_dpe"}
# Dimensions du cube des loyers (le quartier s'ajoutera ici : id_quartier / nom_quartier sont déjà dans le cube)
DIMENSIONS_LOYERS = ["trimestre", "annee_loyer", "arrondissement", "pieces", "epoque"]

def _texte(valeur) -> str:
    """Modalité sous forme de texte : valeur absente -> NON_RENSEIGNE, booléen -> oui / non."""
    if valeur is None:
        return NON_RENSEIGNE
    if isinstance(valeur, bool):
        return "oui" if valeur else "non"
    return str(valeur)


def _cle_tri(texte: str) -> tuple:
    """Ordre des modalités : nombres (arrondissement, pièces) dans l'ordre numérique, textes dans l'ordre alphabétique
    (les libellés de tranche et les trimestres sont déjà préfixés pour l'ordre), NON_RENSEIGNE en dernier."""
    if texte == NON_RENSEIGNE:
        return (2, 0, "")
    try:
        return (0, int(texte), "")
    except ValueError:
        return (1, 0, texte)


def _quantile(valeurs_triees: list[float], q: float) -> float:
    """Quantile par interpolation linéaire d'une liste triée non vide."""
    position = (len(valeurs_triees) - 1) * q
    bas = int(position)
    haut = min(bas + 1, len(valeurs_triees) - 1)
    return valeurs_triees[bas] + (valeurs_triees[haut] - valeurs_triees[bas]) * (position - bas)


def _retenue(ligne: dict, filtres: dict[str, set[str]]) -> bool:
    return all(_texte(ligne[dimension]) in valeurs for dimension, valeurs in filtres.items())


def modalites(lignes: list[dict], dimension: str) -> set[str]:
    """Modalités présentes dans le cube pour une dimension (liste fermée des valeurs de filtre acceptées)."""
    return {_texte(ligne[dimension]) for ligne in lignes}

def modalites_par_dimension(lignes: list[dict], dimensions: list[str]) -> dict[str, list[str]]:
    """Modalités présentes dans le cube pour chaque dimension, dans l'ordre d'affichage (valeurs de filtre proposées)."""
    return {dimension: sorted(modalites(lignes, dimension), key=_cle_tri) for dimension in dimensions}


def pivoter(lignes: list[dict], source: str, axes: list[str], filtres: dict[str, set[str]],
            seuil: int, masquer: bool) -> tuple[list[dict], int]:
    """Regroupe les cellules du cube selon 1 ou 2 axes, après filtres.
    Ventes : effectif, médiane et quartiles du prix au m² (listes de prix fusionnées). DPE : effectif et part en %.
    masquer : les groupes de moins de `seuil` observations sont écartés (accès verrouillé), comptés à part.
    Les parts sont calculées sur les groupes affichés (par modalité du 1er axe s'il y a 2 axes), jamais sur un total
    qui inclurait des groupes masqués. Retourne (cellules triées, nombre de groupes masqués)."""
    compte = COMPTE[source]
    groupes: dict[tuple, dict] = {}
    for ligne in lignes:
        if not _retenue(ligne, filtres):
            continue
        groupe = groupes.setdefault(tuple(_texte(ligne[axe]) for axe in axes), {"n": 0, "prix": []})
        groupe["n"] += ligne[compte]
        if source == "ventes":
            groupe["prix"].extend(ligne["prix_m2"])

    cellules, nb_masquees = [], 0
    for modalites, groupe in groupes.items():
        if masquer and groupe["n"] < seuil:
            nb_masquees += 1
            continue
        cellule = {"modalites": list(modalites), "n": groupe["n"]}
        if source == "ventes":
            prix = sorted(groupe["prix"])
            cellule.update(
                mediane=round(_quantile(prix, 0.5)), q1=round(_quantile(prix, 0.25)), q3=round(_quantile(prix, 0.75)),
            )
        cellules.append(cellule)

    if source == "dpe":
        totaux: dict = {}
        for c in cellules:
            cle = c["modalites"][0] if len(axes) > 1 else None
            totaux[cle] = totaux.get(cle, 0) + c["n"]
        for c in cellules:
            c["part_pct"] = round(c["n"] / totaux[c["modalites"][0] if len(axes) > 1 else None] * 100, 1)

    cellules.sort(key=lambda c: [_cle_tri(m) for m in c["modalites"]])
    return cellules, nb_masquees


def prix_groupe(lignes: list[dict], filtres: dict[str, set[str]]) -> tuple[int, int | None]:
    """Nombre de ventes et prix médian au m² (exact) des cellules retenues par les filtres, listes de prix fusionnées.
    Sert à comparer des groupes que pivoter() garde séparés (F et G ensemble, par exemple)."""
    n = 0
    prix: list[float] = []
    for ligne in lignes:
        if _retenue(ligne, filtres):
            n += ligne["nb_ventes"]
            prix.extend(ligne["prix_m2"])
    return n, (round(_quantile(sorted(prix), 0.5)) if prix else None)



def _mediane_ponderee(couples: list[tuple[float, int]]) -> float:
    """Médiane (basse) de valeurs pondérées par un effectif : couples (valeur, effectif)."""
    couples = sorted(couples)
    moitie = sum(n for _, n in couples) / 2
    cumul = 0
    for valeur, n in couples:
        cumul += n
        if cumul >= moitie:
            return valeur


def _mediane_ou_none(valeurs: list[float], decimales: int, facteur: float = 1) -> float | None:
    return round(_quantile(sorted(valeurs), 0.5) * facteur, decimales) if valeurs else None


def pivoter_loyers(lignes: list[dict], axes: list[str], filtres: dict[str, set[str]],
                   seuil: int, masquer: bool) -> tuple[list[dict], int]:
    """Regroupe les cellules du cube des loyers selon 1 ou 2 axes, après filtres. Les lignes d'un seul statut meublé
    sont attendues (sinon chaque vente serait comptée deux fois). Par groupe : effectif, prix au m² médian, loyers
    médians (pondérés par les ventes), rendements médians en %, parts de ventes en époque ambiguë et en période hétérogène.
    masquer : les groupes de moins de `seuil` ventes sont écartés (accès verrouillé), comptés à part."""
    groupes: dict[tuple, dict] = {}
    for ligne in lignes:
        if not _retenue(ligne, filtres):
            continue
        g = groupes.setdefault(tuple(_texte(ligne[axe]) for axe in axes), {
            "n": 0, "ambigues": 0, "heterogenes": 0, "prix": [], "rendement_reference": [], "rendement_majore": [],
            "loyer_reference": [], "loyer_majore": [], "loyer_minore": [],
        })
        n = ligne["nb_ventes"]
        g["n"] += n
        g["ambigues"] += n if ligne["epoque_ambigue"] else 0
        g["heterogenes"] += n if ligne["periode_heterogene"] else 0
        g["prix"].extend(ligne["prix_m2"])
        g["rendement_reference"].extend(ligne["rendement_reference"])
        g["rendement_majore"].extend(ligne["rendement_majore"])
        for loyer in ("loyer_reference", "loyer_majore", "loyer_minore"):
            if ligne[loyer] is not None:
                g[loyer].append((ligne[loyer], n))

    cellules, nb_masquees = [], 0
    for modalites, g in groupes.items():
        if masquer and g["n"] < seuil:
            nb_masquees += 1
            continue
        cellules.append({
            "modalites": list(modalites),
            "n": g["n"],
            "prix_m2_median": _mediane_ou_none(g["prix"], 0),
            "loyer_reference": round(_mediane_ponderee(g["loyer_reference"]), 1) if g["loyer_reference"] else None,
            "loyer_majore": round(_mediane_ponderee(g["loyer_majore"]), 1) if g["loyer_majore"] else None,
            "loyer_minore": round(_mediane_ponderee(g["loyer_minore"]), 1) if g["loyer_minore"] else None,
            "rendement_reference_pct": _mediane_ou_none(g["rendement_reference"], 1, 100),
            "rendement_majore_pct": _mediane_ou_none(g["rendement_majore"], 1, 100),
            "part_epoque_ambigue_pct": round(g["ambigues"] / g["n"] * 100, 1),
            "part_periode_heterogene_pct": round(g["heterogenes"] / g["n"] * 100, 1),
        })
    cellules.sort(key=lambda c: [_cle_tri(m) for m in c["modalites"]])
    return cellules, nb_masquees


def recouvrement_typologie(lignes: list[dict], filtres: dict[str, set[str]]) -> float | None:
    """Part en % des DPE avec une typologie (pièces renseignées), hors filtre sur les pièces. None si aucun DPE."""
    autres = {dimension: valeurs for dimension, valeurs in filtres.items() if dimension != "pieces"}
    total = avec = 0
    for ligne in lignes:
        if _retenue(ligne, autres):
            total += ligne["nb_dpe"]
            if ligne["pieces"] is not None:
                avec += ligne["nb_dpe"]
    return round(avec / total * 100, 1) if total else None


def resume(lignes: list[dict]) -> dict | None:
    """Date de mise à jour et plage de trimestres couvertes par le cube. None si le cube est vide."""
    if not lignes:
        return None
    return {
        "date_maj": max(l["date_maj"] for l in lignes),
        "trimestre_min": min(l["trimestre"] for l in lignes),
        "trimestre_max": max(l["trimestre"] for l in lignes),
    }
