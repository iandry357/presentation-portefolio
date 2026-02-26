from sqlalchemy import (
    Column, Integer, Float, Text,
    DateTime, JSON, ForeignKey, CheckConstraint
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class JobEnriched(Base):
    __tablename__ = "job_enriched"

    id             = Column(Integer, primary_key=True)

    # Référence offre brute
    job_offer_id   = Column(Integer, ForeignKey("job_offers.id", ondelete="CASCADE"), nullable=False, index=True)

    # Score pgvector interne (jamais exposé au frontend)
    score          = Column(Float, nullable=False, default=0.0, index=True)

    # Résultats du Crew
    parsed_data    = Column(JSON)     # Agent Parser : salaire parsé, stack, expérience numérique...
    analysis       = Column(JSON)     # Agent Analyste : points forts/faibles vs profil
    summary        = Column(Text)     # Agent Rédacteur : fiche synthétique rédigée

    # Traçabilité des prompts et recalculs
    initial_prompt    = Column(Text)
    recalcul_history  = Column(JSON, default=list)
    recalcul_count    = Column(Integer, nullable=False, default=0)

    # Timestamps
    created_at     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at     = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relation ORM vers l'offre brute
    job_offer      = relationship("JobOffer", backref="enriched", lazy="selectin")

    __table_args__ = (
        CheckConstraint(
            "recalcul_count <= 3",
            name="job_enriched_recalcul_max_check"
        ),
    )

    def __repr__(self):
        return f"<JobEnriched job_offer_id={self.job_offer_id} score={self.score} recalcul={self.recalcul_count}/3>"