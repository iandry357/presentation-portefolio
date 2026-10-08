from sqlalchemy import Column, Integer, String, DateTime, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base


class AccessToken(Base):
    """Jeton de privilège (seul le hash SHA-256 hex est stocké)"""
    __tablename__ = "access_tokens"

    id = Column(Integer, primary_key=True)
    token_hash = Column(String(64), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)


class AccessAttempt(Base):
    """Compteur d'échecs anti brute-force, clé = cookie visiteur"""
    __tablename__ = "access_attempts"

    visitor_id = Column(UUID(as_uuid=True), primary_key=True)
    failed_count = Column(Integer, nullable=False, default=0)
    blocked_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, index=True)

    # Contrainte CHECK — alignée avec la migration SQL
    __table_args__ = (
        CheckConstraint("failed_count >= 0", name="access_attempts_failed_count_check"),
    )
