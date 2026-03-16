"""
Schémas Pydantic pour CRUD CV (expériences, projets, compétences)
"""
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from fastapi import HTTPException, Header, BackgroundTasks
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from typing import List


# ============================================================================
# SKILLS
# ============================================================================

class SkillResponse(BaseModel):
    """Schéma de réponse pour une compétence"""
    id: int
    name: str
    category: Optional[str] = None
    proficiency_level: Optional[str] = None

    class Config:
        from_attributes = True


# ============================================================================
# PROJECTS
# ============================================================================

class ProjectBase(BaseModel):
    """Champs communs pour un projet"""
    name: str = Field(..., min_length=1, max_length=255)
    project_type: str = Field(..., min_length=1, max_length=50)
    description: str = Field(..., min_length=1)
    objective: str = Field(..., min_length=1)
    problem: str = Field(..., min_length=1)
    solution: str = Field(..., min_length=1)
    results: str = Field(..., min_length=1)
    impact: str = Field(..., min_length=1)
    stack: str = Field(..., min_length=1)
    collaborators: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    duration_months: Optional[int] = None


class ProjectCreate(ProjectBase):
    """Schéma pour créer un projet (dans une expérience)"""
    pass


class ProjectUpdate(BaseModel):
    """Schéma pour modifier un projet"""
    id: int
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    project_type: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = Field(None, min_length=1)
    objective: Optional[str] = Field(None, min_length=1)
    problem: Optional[str] = Field(None, min_length=1)
    solution: Optional[str] = Field(None, min_length=1)
    results: Optional[str] = Field(None, min_length=1)
    impact: Optional[str] = Field(None, min_length=1)
    stack: Optional[str] = Field(None, min_length=1)
    collaborators: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    duration_months: Optional[int] = None


class ProjectResponse(ProjectBase):
    """Schéma de réponse pour un projet"""
    id: int
    experience_id: int
    embedding_status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# EXPERIENCES
# ============================================================================

class ExperienceBase(BaseModel):
    """Champs communs pour une expérience"""
    company: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., min_length=1, max_length=255)
    mission_type: str = Field(..., min_length=1, max_length=50)
    location: str = Field(..., min_length=1, max_length=255)
    start_date: date
    end_date: Optional[date] = None
    duration_months: Optional[int] = None
    context: str = Field(..., min_length=1)
    is_stage: bool = False


class ExperienceCreate(ExperienceBase):
    """Schéma pour créer une expérience"""
    projects: List[ProjectCreate] = []
    skill_ids: List[int] = []


class ExperienceUpdate(BaseModel):
    """Schéma pour modifier une expérience"""
    company: Optional[str] = Field(None, min_length=1, max_length=255)
    role: Optional[str] = Field(None, min_length=1, max_length=255)
    mission_type: Optional[str] = Field(None, min_length=1, max_length=50)
    location: Optional[str] = Field(None, min_length=1, max_length=255)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    duration_months: Optional[int] = None
    context: Optional[str] = Field(None, min_length=1)
    is_stage: Optional[bool] = None
    projects: Optional[List[ProjectUpdate]] = None
    skill_ids: Optional[List[int]] = None


class ExperienceResponse(ExperienceBase):
    """Schéma de réponse pour une expérience"""
    id: int
    embedding_status: str
    projects: List[ProjectResponse] = []
    skills: List[SkillResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# LISTE & RÉSUMÉS
# ============================================================================

class ExperienceListItem(BaseModel):
    """Schéma pour liste des expériences (sans détails projets)"""
    id: int
    company: str
    role: str
    start_date: date
    end_date: Optional[date] = None
    location: str
    is_stage: bool
    embedding_status: str
    project_count: int = 0

    class Config:
        from_attributes = True