"""
Modèles SQLAlchemy pour les tables CV
"""
from datetime import date, datetime
from typing import List, Optional
from sqlalchemy import (
    Boolean, Column, Date, ForeignKey, Integer, 
    String, Text, TIMESTAMP, ARRAY
)
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.core.database import Base


# ============================================================================
# TABLE: informations
# ============================================================================

class Information(Base):
    __tablename__ = "informations"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String(255), nullable=False)
    prenom = Column(String(255))
    prononciation = Column(String(255))
    date_naissance = Column(Date)
    pays_naissance = Column(String(255))
    location = Column(String(255))
    passion = Column(Text)
    embedding = Column(Vector(1024))
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================================
# TABLE: skills
# ============================================================================

class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    category = Column(String(100))
    proficiency_level = Column(String(50))
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)

    # Relationships
    experiences = relationship("Experience", secondary="experience_skills", back_populates="skills")
    projects = relationship("Project", secondary="project_skills", back_populates="skills")


# ============================================================================
# TABLE: experiences
# ============================================================================

class Experience(Base):
    __tablename__ = "experiences"

    id = Column(Integer, primary_key=True, index=True)
    company = Column(String(255), nullable=False)
    role = Column(String(255), nullable=False)
    mission_type = Column(String(50))
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, index=True)
    duration_months = Column(Integer)
    location = Column(String(255))
    context = Column(Text)
    technologies = Column(ARRAY(Text))
    is_stage = Column(Boolean, default=False)
    embedding = Column(Vector(1024))
    embedding_status = Column(String(20), nullable=False, default="done")
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    projects = relationship("Project", back_populates="experience", cascade="all, delete-orphan")
    skills = relationship("Skill", secondary="experience_skills", back_populates="experiences")


# ============================================================================
# TABLE: projects
# ============================================================================

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    experience_id = Column(Integer, ForeignKey("experiences.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    objective = Column(Text)
    problem = Column(Text)
    solution = Column(Text)
    results = Column(Text)
    impact = Column(Text)
    stack = Column(Text)
    start_date = Column(Date)
    end_date = Column(Date)
    duration_months = Column(Integer)
    collaborators = Column(Text)
    project_type = Column(String(50))
    embedding = Column(Vector(1024))
    embedding_status = Column(String(20), nullable=False, default="done")
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    experience = relationship("Experience", back_populates="projects")
    skills = relationship("Skill", secondary="project_skills", back_populates="projects")


# ============================================================================
# TABLE: formations
# ============================================================================

class Formation(Base):
    __tablename__ = "formations"

    id = Column(Integer, primary_key=True, index=True)
    institution = Column(String(255), nullable=False)
    degree = Column(String(255), nullable=False)
    field = Column(String(255))
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, index=True)
    location = Column(String(255))
    description = Column(Text)
    key_learnings = Column(Text)
    embedding = Column(Vector(1024))
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================================
# TABLES: Many-to-Many relations
# ============================================================================

class ExperienceSkill(Base):
    __tablename__ = "experience_skills"

    experience_id = Column(Integer, ForeignKey("experiences.id", ondelete="CASCADE"), primary_key=True)
    skill_id = Column(Integer, ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)


class ProjectSkill(Base):
    __tablename__ = "project_skills"

    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    skill_id = Column(Integer, ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)