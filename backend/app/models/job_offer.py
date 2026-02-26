from sqlalchemy import (
    Column, Integer, String, Text, Float,
    DateTime, JSON, CheckConstraint
)
from sqlalchemy.sql import func
from app.core.database import Base


class JobOffer(Base):
    __tablename__ = "job_offers"

    id                   = Column(Integer, primary_key=True)

    # Identifiant France Travail
    ft_id                = Column(String(50), nullable=False, unique=True, index=True)

    # Infos principales
    title                = Column(String(255), nullable=False)
    description          = Column(Text)
    contract_type        = Column(String(50), index=True)
    contract_label       = Column(String(100))
    work_time            = Column(String(100))

    # Expérience
    experience_code      = Column(String(10))
    experience_label     = Column(String(255))

    # ROME
    rome_code            = Column(String(10), index=True)

    # Localisation
    location_label       = Column(String(255))
    location_postal_code = Column(String(10), index=True)
    location_lat         = Column(Float)
    location_lng         = Column(Float)

    # Entreprise
    company_name         = Column(String(255))
    company_description  = Column(Text)
    company_url          = Column(Text)

    # Salaire (libellé brut - parsing par le Crew)
    salary_label         = Column(String(255))

    # Secteur
    sector_label         = Column(String(255))
    naf_code             = Column(String(20))

    # URLs
    offer_url            = Column(Text)

    # Dates France Travail
    ft_published_at      = Column(DateTime(timezone=True), index=True)
    ft_updated_at        = Column(DateTime(timezone=True))

    # Données brutes complètes
    raw_data             = Column(JSON, nullable=False)

    # Suivi statut
    status               = Column(
                               String(20),
                               nullable=False,
                               default="nouveau",
                               index=True
                           )
    last_seen_at         = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    applied_at           = Column(DateTime(timezone=True))

    # Timestamps
    created_at           = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at           = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('nouveau', 'existant', 'ferme', 'consulte', 'postule')",
            name="job_offers_status_check"
        ),
    )

    def __repr__(self):
        return f"<JobOffer ft_id={self.ft_id} title={self.title} status={self.status}>"