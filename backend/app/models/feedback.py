from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class PageFeedback(Base):
    """Feedback global par page/visite"""
    __tablename__ = "page_feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, nullable=True)  # FK future vers users
    page_route = Column(String(255), nullable=False)
    page_type = Column(String(50), nullable=False, index=True)
    rating = Column(Integer, nullable=False)
    job_offer_id = Column(Integer, ForeignKey("job_offers.id", ondelete="SET NULL"), nullable=True, index=True)
    company_profile_id = Column(Integer, ForeignKey("company_profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationships
    answers = relationship("FeedbackAnswer", back_populates="feedback", cascade="all, delete-orphan", lazy="selectin")
    job_offer = relationship("JobOffer", foreign_keys=[job_offer_id], lazy="selectin")
    company_profile = relationship("CompanyProfile", foreign_keys=[company_profile_id], lazy="selectin")

    # Constraint
    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="check_rating_range"),
    )


class FeedbackAnswer(Base):
    """Réponse à une question spécifique du feedback"""
    __tablename__ = "feedback_answers"

    id = Column(Integer, primary_key=True, index=True)
    feedback_id = Column(Integer, ForeignKey("page_feedbacks.id", ondelete="CASCADE"), nullable=False, index=True)
    question_key = Column(String(100), nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    feedback = relationship("PageFeedback", back_populates="answers")