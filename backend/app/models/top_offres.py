from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.sql import func
from app.core.database import Base


class TopOffreDecision(Base):
    """Décision de l'utilisateur sur une offre du top du jour (clé = id_unique BigQuery).
    Les états brouillon / enregistree se lisent via job_offer_id -> job_offers.status."""
    __tablename__ = "top_offres_decisions"

    id_unique = Column(Text, primary_key=True)
    decision = Column(String(20), nullable=False)
    job_offer_id = Column(Integer, ForeignKey("job_offers.id", ondelete="SET NULL"), nullable=True, index=True)
    groupe_doublon = Column(Text, nullable=False, index=True)
    titre_normalise = Column(Text, nullable=False, default="")
    entreprise_normalise = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Contrainte CHECK — alignée avec la migration SQL
    __table_args__ = (
        CheckConstraint("decision IN ('pas_interesse', 'interesse')", name="top_offres_decisions_decision_check"),
    )


class TopOffreTypeEntreprise(Base):
    """Type d'entreprise corrigé par l'utilisateur (clé = nom normalisé, comme le mart)."""
    __tablename__ = "top_offres_types_entreprise"

    nom_normalise = Column(Text, primary_key=True)
    type_entreprise = Column(String(30), nullable=False)
    commentaire = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Contrainte CHECK — alignée avec la migration SQL
    __table_args__ = (
        CheckConstraint(
            "type_entreprise IN ('esn', 'conseil', 'esn_conseil', 'cabinet_recrutement', 'client_final')",
            name="top_offres_types_entreprise_type_check",
        ),
    )
