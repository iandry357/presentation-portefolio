import re
import unicodedata


def normaliser(texte: str | None) -> str:
    """Normalisation d'un texte (titre, entreprise) : minuscules, sans accents ni ponctuation,
    espaces réduits, mentions de genre supprimées.

    Copie de `normaliser` du worker Top Offres (realisations/top-offres/pipeline/transformation/entreprises.py),
    elle-même alignée sur la macro dbt `normaliser` : les trois doivent rester synchronisées."""
    if not texte:
        return ""
    decompose = unicodedata.normalize("NFD", texte.lower())
    sans_accents = "".join(c for c in decompose if not unicodedata.category(c).startswith("M"))
    sans_genre = re.sub(r"\b(h|f|m)\s*[/-]\s*(h|f)(\s*[/-]\s*(x|d|nb))?\b", " ", sans_accents)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", sans_genre)).strip()
