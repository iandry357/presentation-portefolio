"""
Contrôle d'accès public / privé.

Deux cookies httpOnly, indépendants du système de session du chat :
  - cookie visiteur : sert uniquement de clé au compteur anti brute-force ;
  - cookie jeton    : généré par le serveur, seule clé donnant accès au privé.
Le jeton n'est stocké qu'haché (SHA-256) en base ; la fenêtre est glissante.
Les fonctions qui écrivent en base commitent elles-mêmes.
"""

import hashlib
import hmac
import secrets
import uuid
from typing import Optional

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import and_, case, delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.time_utils import add_minutes, now_utc, seconds_until
from app.models.access_token import AccessAttempt, AccessToken

# ─── Paramètres configurables ────────────────────────────────────────────────
ACCESS_TOKEN_TTL_MINUTES = 15        # durée de vie glissante du jeton
MAX_FAILED_ATTEMPTS = 5              # échecs avant blocage
BLOCK_DURATION_MINUTES = 10          # durée du blocage
TOKEN_BYTES = 32                     # taille du jeton opaque
VISITOR_COOKIE_NAME = "visitor_id"
ACCESS_COOKIE_NAME = "access_token"
VISITOR_COOKIE_MAX_AGE_DAYS = 30
ATTEMPTS_RETENTION_DAYS = 30         # purge des compteurs inactifs (= vie du cookie visiteur)


# ─── Jeton ───────────────────────────────────────────────────────────────────

def generate_token() -> str:
    """Jeton opaque aléatoire, URL-safe."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    """SHA-256 hex du jeton (seule forme stockée en base)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ─── Cookies ─────────────────────────────────────────────────────────────────

def _cookie_flags() -> dict:
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": not settings.is_dev,   # localhost est en http
        "path": "/",
    }


def set_visitor_cookie(response: Response, visitor_id: uuid.UUID) -> None:
    response.set_cookie(
        VISITOR_COOKIE_NAME,
        str(visitor_id),
        max_age=VISITOR_COOKIE_MAX_AGE_DAYS * 24 * 3600,
        **_cookie_flags(),
    )


def set_access_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        ACCESS_COOKIE_NAME,
        token,
        max_age=ACCESS_TOKEN_TTL_MINUTES * 60,
        **_cookie_flags(),
    )


def clear_access_cookie(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE_NAME, **_cookie_flags())


def get_or_create_visitor_id(request: Request, response: Response) -> uuid.UUID:
    """Lit le cookie visiteur ; s'il est absent ou invalide, en génère un et le pose."""
    raw = request.cookies.get(VISITOR_COOKIE_NAME)
    if raw:
        try:
            return uuid.UUID(raw)
        except ValueError:
            pass
    visitor_id = uuid.uuid4()
    set_visitor_cookie(response, visitor_id)
    return visitor_id


# ─── Vérification du code ────────────────────────────────────────────────────

def verify_code(submitted: str) -> bool:
    """Comparaison à temps constant avec le secret serveur."""
    expected = settings.ACCESS_CODE
    if not expected:
        return False
    return hmac.compare_digest(submitted.encode("utf-8"), expected.encode("utf-8"))


# ─── Anti brute-force ────────────────────────────────────────────────────────

async def get_block_seconds(db: AsyncSession, visitor_id: uuid.UUID) -> int:
    """Secondes de blocage restantes pour ce visiteur (0 = non bloqué)."""
    result = await db.execute(
        select(AccessAttempt.blocked_until).where(AccessAttempt.visitor_id == visitor_id)
    )
    blocked_until = result.scalar_one_or_none()
    return seconds_until(blocked_until) if blocked_until else 0


async def register_failure(db: AsyncSession, visitor_id: uuid.UUID) -> int:
    """
    Enregistre un échec (upsert atomique) et retourne les secondes de blocage
    restantes (0 = pas bloqué). Si un blocage précédent est expiré, le compteur
    repart de 1.
    """
    now = now_utc()
    block_until = add_minutes(now, BLOCK_DURATION_MINUTES)

    block_expired = and_(
        AccessAttempt.blocked_until.is_not(None),
        AccessAttempt.blocked_until <= now,
    )
    new_count = case((block_expired, 1), else_=AccessAttempt.failed_count + 1)

    stmt = (
        pg_insert(AccessAttempt)
        .values(
            visitor_id=visitor_id,
            failed_count=1,
            blocked_until=block_until if MAX_FAILED_ATTEMPTS <= 1 else None,
        )
        .on_conflict_do_update(
            index_elements=[AccessAttempt.visitor_id],
            set_={
                "failed_count": new_count,
                "blocked_until": case((new_count >= MAX_FAILED_ATTEMPTS, block_until), else_=None),
            },
        )
        .returning(AccessAttempt.blocked_until)
    )
    result = await db.execute(stmt)
    blocked_until = result.scalar_one()
    await db.commit()
    return seconds_until(blocked_until) if blocked_until else 0


async def reset_failures(db: AsyncSession, visitor_id: uuid.UUID) -> None:
    """Remise à zéro immédiate (code correct)."""
    await db.execute(delete(AccessAttempt).where(AccessAttempt.visitor_id == visitor_id))
    await db.commit()


# ─── Création, purge et validation du jeton ──────────────────────────────────

async def purge_expired(db: AsyncSession) -> None:
    """Supprime les jetons expirés et les compteurs inactifs et non bloqués."""
    now = now_utc()
    await db.execute(delete(AccessToken).where(AccessToken.expires_at <= now))
    await db.execute(
        delete(AccessAttempt).where(
            AccessAttempt.updated_at < add_minutes(now, -ATTEMPTS_RETENTION_DAYS * 24 * 60),
            (AccessAttempt.blocked_until.is_(None)) | (AccessAttempt.blocked_until <= now),
        )
    )


async def create_access_token(db: AsyncSession) -> str:
    """Purge opportuniste, puis crée un jeton ; retourne le jeton en clair (pour le cookie)."""
    await purge_expired(db)
    token = generate_token()
    db.add(AccessToken(
        token_hash=hash_token(token),
        expires_at=add_minutes(now_utc(), ACCESS_TOKEN_TTL_MINUTES),
    ))
    await db.commit()
    return token


async def _touch_token(db: AsyncSession, token: str) -> bool:
    """Valide le jeton ET repousse son expiration, en une seule requête atomique."""
    now = now_utc()
    result = await db.execute(
        update(AccessToken)
        .where(AccessToken.token_hash == hash_token(token), AccessToken.expires_at > now)
        .values(expires_at=add_minutes(now, ACCESS_TOKEN_TTL_MINUTES))
        .returning(AccessToken.id)
    )
    found = result.first() is not None
    await db.commit()
    return found


async def revoke_access_token(db: AsyncSession, token: str) -> None:
    """Supprime le jeton en base (verrouillage manuel)."""
    await db.execute(delete(AccessToken).where(AccessToken.token_hash == hash_token(token)))
    await db.commit()


# ─── Dépendances FastAPI ─────────────────────────────────────────────────────

async def get_access_state(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> bool:
    """
    Garde souple : indique seulement si l'accès est déverrouillé.
    Si oui, la fenêtre est prolongée et le cookie ré-émis (Max-Age rafraîchi).
    FastAPI met la dépendance en cache : une seule vérification par requête,
    même déclarée à la fois sur le routeur et sur la route.
    """
    token: Optional[str] = request.cookies.get(ACCESS_COOKIE_NAME)
    if not token:
        return False
    if await _touch_token(db, token):
        set_access_cookie(response, token)
        return True
    clear_access_cookie(response)
    return False


async def get_access_remaining(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[int]:
    """
    Lecture seule : secondes restantes du jeton, ou None s'il est absent ou expiré.
    Ne prolonge pas la fenêtre et ne touche à aucun cookie.
    """
    token: Optional[str] = request.cookies.get(ACCESS_COOKIE_NAME)
    if not token:
        return None
    result = await db.execute(
        select(AccessToken.expires_at).where(
            AccessToken.token_hash == hash_token(token),
            AccessToken.expires_at > now_utc(),
        )
    )
    expires_at = result.scalar_one_or_none()
    return seconds_until(expires_at) if expires_at else None


async def require_access(unlocked: bool = Depends(get_access_state)) -> None:
    """Garde stricte : 403 si l'accès n'est pas déverrouillé."""
    if not unlocked:
        raise HTTPException(status_code=403, detail="Accès privé : code requis")
