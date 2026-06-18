import json
import os
from collections import defaultdict
from datetime import datetime
from bq_client import get_clinical_trials

RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results", "forecasting.json")
CLUSTERING_PATH = os.path.join(os.path.dirname(__file__), "results", "clustering.json")

KNOWN_PHASES = ["PHASE1", "PHASE2", "PHASE3", "PHASE4", "PHASE1, PHASE2", "PHASE2, PHASE3"]


def _parse_date(date_str: str) -> datetime | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(str(date_str), fmt)
        except ValueError:
            continue
    return None


def _volume_by_year(trials: list) -> list:
    counts = defaultdict(int)
    for t in trials:
        start = _parse_date(t.get("metadata", {}).get("start_date"))
        if start:
            counts[start.year] += 1
    return [{"year": y, "count": counts[y]} for y in sorted(counts)]


def _phases_by_year(trials: list) -> list:
    phase_year = defaultdict(lambda: defaultdict(int))
    for t in trials:
        phase = t.get("metadata", {}).get("phase")
        start = _parse_date(t.get("metadata", {}).get("start_date"))
        if phase in KNOWN_PHASES and start:
            phase_year[start.year][phase] += 1

    years = sorted(phase_year.keys())
    return [
        {"year": y, "phases": dict(phase_year[y])}
        for y in years
    ]


def _duration_by_cluster(trials: list, clustering: dict) -> list:
    trial_cluster = {t["id"]: t for t in clustering.get("trials", [])}
    cluster_labels = {c["cluster_id"]: c["label"] for c in clustering.get("clusters", [])}

    cluster_durations = defaultdict(list)
    for t in trials:
        meta = t.get("metadata", {})
        # start = _parse_date(meta.get("start_date"))
        start = _parse_date(t.get("date"))
        end = _parse_date(meta.get("completion_date"))
        trial_info = trial_cluster.get(t["id"])
        if start and end and end > start and trial_info:
            duration_months = (end.year - start.year) * 12 + (end.month - start.month)
            cluster_durations[trial_info["cluster_id"]].append(duration_months)

    result = []
    for cid, durations in sorted(cluster_durations.items()):
        avg = round(sum(durations) / len(durations), 1)
        result.append({
            "cluster_id": cid,
            "label": cluster_labels.get(cid, f"Cluster {cid}"),
            "avg_duration_months": avg,
            "trial_count": len(durations),
        })
    return result


def _bayesian_forecast(volume_by_year: list, target_year: int = 2026) -> dict:
    """
    Estimation bayésienne du volume d'essais restants pour target_year.
    Approche :
      - Taux mensuel estimé sur l'historique (années complètes)
      - Modèle conjugué Poisson-Gamma mis à jour sur ce taux
      - Projection sur les mois restants de l'année cible
      - Résultat : déjà observés + restants prédits = total fin d'année
    """
    import math

    current_year = datetime.now().year
    current_month = datetime.now().month

    # Années complètes uniquement (hors année cible et année courante si différente)
    historical = [
        d for d in volume_by_year
        if d["year"] < current_year and d["year"] >= 2010
    ]

    # Volume déjà observé dans l'année cible
    current_year_data = next(
        (d for d in volume_by_year if d["year"] == target_year), None
    )
    already_observed = current_year_data["count"] if current_year_data else 0

    if not historical:
        return {
            "already_observed": already_observed,
            "predicted_remaining": None,
            "total_predicted": None,
            "ci_lower_95": None,
            "ci_upper_95": None,
            "months_remaining": None,
            "n_years_used": 0,
            "avg_monthly_rate": None,
        }

    # Taux mensuel historique
    monthly_counts = [d["count"] / 12.0 for d in historical]
    n = len(monthly_counts)
    total_monthly = sum(monthly_counts)

    # Mois restants dans l'année cible (mois courant non complet exclu)
    months_remaining = 12 - current_month

    # Prior faiblement informatif Gamma(1, 1)
    alpha_prior = 1.0
    beta_prior = 1.0

    # Posterior Gamma mis à jour sur les taux mensuels historiques
    alpha_post = alpha_prior + total_monthly
    beta_post = beta_prior + n

    # Taux mensuel postérieur
    monthly_rate = alpha_post / beta_post
    monthly_variance = alpha_post * (1 + beta_post) / (beta_post ** 2)

    # Projection sur les mois restants
    predicted_remaining_mean = monthly_rate * months_remaining
    predicted_remaining_std = math.sqrt(monthly_variance * months_remaining)

    predicted_remaining = round(predicted_remaining_mean)
    ci_lower = max(0, round(predicted_remaining_mean - 1.96 * predicted_remaining_std))
    ci_upper = round(predicted_remaining_mean + 1.96 * predicted_remaining_std)

    total_predicted = already_observed + predicted_remaining
    total_ci_lower = already_observed + ci_lower
    total_ci_upper = already_observed + ci_upper

    return {
        "already_observed": already_observed,
        "predicted_remaining": predicted_remaining,
        "total_predicted": total_predicted,
        "total_ci_lower": total_ci_lower,
        "total_ci_upper": total_ci_upper,
        "months_remaining": months_remaining,
        "n_years_used": n,
        "avg_monthly_rate": round(monthly_rate, 2),
    }


def run() -> dict:
    trials = get_clinical_trials()

    clustering = {}
    if os.path.exists(CLUSTERING_PATH):
        with open(CLUSTERING_PATH) as f:
            clustering = json.load(f)
    else:
        print("Warning — clustering.json non trouvé, durée par cluster ignorée")

    volume_by_year = _volume_by_year(trials)
    phases_by_year = _phases_by_year(trials)
    duration_by_cluster = _duration_by_cluster(trials, clustering)

    bayesian_forecast = _bayesian_forecast(volume_by_year)

    result = {
        "total_trials": len(trials),
        "volume_by_year": volume_by_year,
        "phases_by_year": phases_by_year,
        "duration_by_cluster": duration_by_cluster,
        "bayesian_forecast": bayesian_forecast,
    }

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(f"Forecasting done — {len(trials)} trials analysés")
    print(f"  Volume par année : {len(volume_by_year)} années")
    print(f"  Phases par année : {len(phases_by_year)} années")
    print(f"  Durée par cluster : {len(duration_by_cluster)} clusters")

    return result


if __name__ == "__main__":
    run()