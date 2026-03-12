from sqlalchemy import (
    Column, Integer, String, Text, Float,
    DateTime, JSON, CheckConstraint, ForeignKey
)
from sqlalchemy.sql import func
from app.core.database import Base
from sqlalchemy.orm import relationship


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
    rome_libelle         = Column(String(255), nullable=True)
    rome_source_intitule = Column(String(255), nullable=True, index=True)
    source_branch        = Column(String(10), nullable=True)

    # Localisation
    location_label       = Column(String(255))
    location_postal_code = Column(String(10), index=True)
    location_lat         = Column(Float)
    location_lng         = Column(Float)

    # Entreprise
    company_name         = Column(String(255))
    company_description  = Column(Text)
    company_profile_id   = Column(Integer, ForeignKey("company_profiles.id"), nullable=True, index=True)
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

    notes                = Column(Text, nullable=True)

    

    # Timestamps
    created_at           = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at           = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('nouveau', 'existant', 'ferme', 'consulte', 'postule', 'enregistre')",
            name="job_offers_status_check"
        ),
        CheckConstraint(
            "label IN ('basique', 'medium', 'priorité')",
            name="job_offers_label_check"
        ),
    )

    label = Column(String(20), nullable=False, index=True)
    score = Column(Float, nullable=False)

    enriched = relationship("JobEnriched", back_populates="job_offer", uselist=False, lazy="selectin")

    company_profile = relationship("CompanyProfile", back_populates="jobs", lazy="selectin")

    def __repr__(self):
        return f"<JobOffer ft_id={self.ft_id} title={self.title} status={self.status}>"