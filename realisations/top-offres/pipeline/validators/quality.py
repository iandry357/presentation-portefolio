CATEGORIES = ("coeur", "adjacent", "hors_cible")
ALERTES_AUTORISEES = ("salaire_incoherent", "titre_ambigu", "intermediaire", "seniorite_incertaine", "autre")
RAISON_MAX = 200


def valider_evaluation(evaluation: dict) -> dict:
    """Contrôle l'évaluation d'une offre par le LLM ; lève ValueError si elle est invalide.
    Une raison trop longue est tronquée à RAISON_MAX caractères."""
    score = evaluation.get("score")
    if isinstance(score, float) and score.is_integer():
        score = int(score)
    if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 100:
        raise ValueError(f"score invalide : {score!r}")
    categorie = evaluation.get("categorie")
    if categorie not in CATEGORIES:
        raise ValueError(f"categorie invalide : {categorie!r}")
    raison = evaluation.get("raison")
    if not isinstance(raison, str) or not raison.strip():
        raise ValueError("raison vide ou invalide")
    alertes = evaluation.get("alertes")
    if not isinstance(alertes, list) or any(a not in ALERTES_AUTORISEES for a in alertes):
        raise ValueError(f"alertes invalides : {alertes!r}")
    return {
        "score": score,
        "categorie": categorie,
        "raison": raison.strip()[:RAISON_MAX],
        "alertes": list(dict.fromkeys(alertes)),
    }
