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
