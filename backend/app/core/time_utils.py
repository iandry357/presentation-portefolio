"""
Utilitaires de date/heure partagés.

Règle : toute date manipulée dans le backend est timezone-aware en UTC
(colonnes TIMESTAMPTZ). Les dates naïves sont supposées UTC et normalisées
ici, jamais ailleurs.
"""

import math
from datetime import datetime, timedelta, timezone


def now_utc() -> datetime:
    """Heure courante, timezone-aware UTC."""
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    """Normalise vers UTC aware. Une date naïve est supposée déjà en UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def add_minutes(dt: datetime, minutes: float) -> datetime:
    """Retourne dt décalée de `minutes` (négatif accepté), en UTC aware."""
    return ensure_utc(dt) + timedelta(minutes=minutes)


def seconds_until(dt: datetime) -> int:
    """Secondes restantes avant dt, arrondies au supérieur ; 0 si dt est passée."""
    delta = (ensure_utc(dt) - now_utc()).total_seconds()
    return max(0, math.ceil(delta))


def to_iso(dt: datetime) -> str:
    """Sérialise en ISO 8601 UTC, suffixe 'Z' (ex. 2026-10-08T14:30:00Z)."""
    return ensure_utc(dt).isoformat().replace("+00:00", "Z")


def from_iso(value: str) -> datetime:
    """Lit une date ISO 8601 (avec ou sans 'Z' / offset) vers UTC aware."""
    return ensure_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
