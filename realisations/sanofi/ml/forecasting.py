import json
import os
from collections import defaultdict
from datetime import datetime
from bq_client import get_clinical_trials
import numpy as np
from scipy.optimize import minimize

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
    GLM Poisson bayésien avec trend temporel + approximation de Laplace.

    Modèle :
      λ(t) = exp(α + β·t)        — taux annuel, t = année recentrée sur 2010
      y_t  ~ Poisson(λ(t))       — comptage annuel observé
      priors gaussiens faibles sur α, β

    Inférence :
      - MAP (mode du posterior) via minimisation de la log-vraisemblance négative pénalisée
      - posterior approché par une gaussienne N(MAP, H⁻¹) où H = Hessienne au mode
      - échantillonnage du posterior → distribution de λ(2026) → projection mois restants

    Le déjà-observé 2026 reste le point de départ ; on ne prédit que le restant.
    """
    current_year = datetime.now().year
    current_month = datetime.now().month

    historical = sorted(
        [d for d in volume_by_year if d["year"] < current_year and d["year"] >= 2010],
        key=lambda d: d["year"]
    )

    current_year_data = next(
        (d for d in volume_by_year if d["year"] == target_year), None
    )
    already_observed = current_year_data["count"] if current_year_data else 0

    empty = {
        "already_observed": already_observed,
        "predicted_remaining": None,
        "total_predicted": None,
        "total_ci_lower": None,
        "total_ci_upper": None,
        "months_remaining": None,
        "n_years_used": 0,
        "avg_monthly_rate": None,
    }
    if len(historical) < 3:
        return empty

    # Données : t recentré sur 2010, y = comptage annuel
    t = np.array([d["year"] - 2010 for d in historical], dtype=float)
    y = np.array([d["count"] for d in historical], dtype=float)

    # Priors gaussiens faibles : α ~ N(0, 10²), β ~ N(0, 1²)
    prior_var_alpha = 100.0
    prior_var_beta = 1.0

    def neg_log_posterior(params):
        alpha, beta = params
        lam = np.exp(alpha + beta * t)
        # log-vraisemblance Poisson (sans terme log(y!) constant)
        log_lik = np.sum(y * (alpha + beta * t) - lam)
        # log-prior gaussien
        log_prior = -0.5 * (alpha ** 2 / prior_var_alpha + beta ** 2 / prior_var_beta)
        return -(log_lik + log_prior)

    # MAP via optimisation
    init = np.array([np.log(y.mean() + 1e-6), 0.0])
    res = minimize(neg_log_posterior, init, method="BFGS")
    if not res.success:
        return empty

    map_params = res.x
    # Hessienne au mode → covariance posterior = H⁻¹
    cov = res.hess_inv

    # Échantillonnage du posterior gaussien approché
    rng = np.random.default_rng(42)
    samples = rng.multivariate_normal(map_params, cov, size=10000)

    months_remaining = 12 - current_month

    # Pour chaque échantillon (α, β) → λ(2026) annuel → taux mensuel → restant
    t_2026 = target_year - 2010
    lam_2026 = np.exp(samples[:, 0] + samples[:, 1] * t_2026)
    monthly_rate_samples = lam_2026 / 12.0
    remaining_mean_samples = monthly_rate_samples * months_remaining

    # Incertitude Poisson en plus de l'incertitude sur la pente
    remaining_draws = rng.poisson(np.clip(remaining_mean_samples, 0, None))

    predicted_remaining = int(round(np.median(remaining_draws)))
    ci_lower = int(max(0, round(np.percentile(remaining_draws, 2.5))))
    ci_upper = int(round(np.percentile(remaining_draws, 97.5)))

    # Taux mensuel postérieur médian (pour affichage)
    monthly_rate_post = float(np.median(monthly_rate_samples))

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
        "n_years_used": len(historical),
        "avg_monthly_rate": round(monthly_rate_post, 2),
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