from sqlalchemy import (
    Column, Integer, String, Text,
    DateTime, JSON, CheckConstraint, ForeignKey
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class CompanyProfile(Base):
    __tablename__ = "company_profiles"

    # Identité
    id                    = Column(Integer, primary_key=True)
    name                  = Column(String(255), nullable=False, unique=True, index=True)  # nom normalisé
    name_input            = Column(String(255), nullable=False)                           # nom brut saisi

    # Données par couche
    discovery             = Column(JSON, nullable=True)   # Agent 1 : SIREN, URLs référence, famille 1
    legal_data            = Column(JSON, nullable=True)   # Agent 2 : santé financière, activité, image employeur
    actualites            = Column(JSON, nullable=True)   # refresh indépendant : articles, signaux recrutement
    memo                  = Column(Text, nullable=True)   # Agent 3 : mémo Markdown final

    # Statuts par couche
    discovery_status      = Column(String(10), nullable=False, default="pending")
    legal_status          = Column(String(10), nullable=False, default="pending")
    actualites_status     = Column(String(10), nullable=False, default="pending")
    memo_status           = Column(String(10), nullable=False, default="pending")

    # Contrôle mémo
    recalcul_count        = Column(Integer, nullable=False, default=0)
    recalcul_history      = Column(JSON, nullable=False, default=list)

    # Horodatage
    actualites_updated_at = Column(DateTime(timezone=True), nullable=True)
    created_at            = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at            = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Contraintes CHECK — alignées avec la migration SQL
    __table_args__ = (
        CheckConstraint(
            "discovery_status IN ('pending', 'done', 'failed')",
            name="company_profiles_discovery_status_check"
        ),
        CheckConstraint(
            "legal_status IN ('pending', 'done', 'failed')",
            name="company_profiles_legal_status_check"
        ),
        CheckConstraint(
            "actualites_status IN ('pending', 'done', 'failed')",
            name="company_profiles_actualites_status_check"
        ),
        CheckConstraint(
            "memo_status IN ('pending', 'done', 'failed')",
            name="company_profiles_memo_status_check"
        ),
    )

    # Relation vers JobOffer
    jobs = relationship("JobOffer", back_populates="company_profile", lazy="selectin")

    def __repr__(self):
        return f"<CompanyProfile name={self.name} discovery_status={self.discovery_status} memo_status={self.memo_status}>"