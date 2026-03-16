"""
Service CRUD CV - Normalisation, comparaison, régénération embeddings
"""
import re
import asyncio
import logging
from datetime import date
from typing import Dict, Any, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.cv import Experience, Project
from app.services.embeddings import vectorize_query

logger = logging.getLogger(__name__)


# ============================================================================
# NORMALISATION
# ============================================================================

def normalize_text(text: Optional[str]) -> str:
    """
    Normalise un texte pour comparaison :
    - strip début/fin
    - espaces multiples → espace simple
    - retours ligne multiples → double retour
    - lowercase
    """
    if not text:
        return ""
    
    # Strip début/fin
    normalized = text.strip()
    
    # Espaces multiples → espace simple
    normalized = re.sub(r' +', ' ', normalized)
    
    # Retours ligne multiples → double retour
    normalized = re.sub(r'\n{3,}', '\n\n', normalized)
    
    # Lowercase
    normalized = normalized.lower()
    
    return normalized


def normalize_date(d: Optional[date]) -> Optional[str]:
    """Convertit une date en ISO string pour comparaison"""
    return d.isoformat() if d else None


def normalize_experience_dict(exp_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalise un dictionnaire d'expérience pour comparaison.
    Applique normalize_text sur tous les champs texte.
    """
    normalized = {}
    
    # Champs texte
    text_fields = ['company', 'role', 'mission_type', 'location', 'context']
    for field in text_fields:
        normalized[field] = normalize_text(exp_dict.get(field))
    
    # Dates
    normalized['start_date'] = normalize_date(exp_dict.get('start_date'))
    normalized['end_date'] = normalize_date(exp_dict.get('end_date'))
    
    # Booléen
    normalized['is_stage'] = exp_dict.get('is_stage', False)
    
    # Skills (triés pour comparaison stable)
    skill_ids = exp_dict.get('skill_ids', [])
    normalized['skill_ids'] = sorted(skill_ids) if skill_ids else []
    
    # Projets (normalisés et triés par nom)
    projects = exp_dict.get('projects', [])
    normalized['projects'] = sorted(
        [normalize_project_dict(p) for p in projects],
        key=lambda x: x.get('name', '')
    )
    
    return normalized


def normalize_project_dict(proj_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalise un dictionnaire de projet pour comparaison.
    """
    normalized = {}
    
    # Champs texte
    text_fields = [
        'name', 'project_type', 'description', 'objective', 
        'problem', 'solution', 'results', 'impact', 
        'stack', 'collaborators'
    ]
    for field in text_fields:
        normalized[field] = normalize_text(proj_dict.get(field))
    
    # Dates
    normalized['start_date'] = normalize_date(proj_dict.get('start_date'))
    normalized['end_date'] = normalize_date(proj_dict.get('end_date'))
    
    # ID (pour matching dans update)
    if 'id' in proj_dict:
        normalized['id'] = proj_dict['id']
    
    return normalized


# ============================================================================
# COMPARAISON
# ============================================================================

def experiences_are_different(
    old_exp: Dict[str, Any], 
    new_exp: Dict[str, Any]
) -> bool:
    """
    Compare deux versions d'une expérience après normalisation.
    Retourne True si différence détectée.
    """
    old_normalized = normalize_experience_dict(old_exp)
    new_normalized = normalize_experience_dict(new_exp)
    
    return old_normalized != new_normalized


def projects_are_different(
    old_proj: Dict[str, Any], 
    new_proj: Dict[str, Any]
) -> bool:
    """
    Compare deux versions d'un projet après normalisation.
    Retourne True si différence détectée.
    """
    old_normalized = normalize_project_dict(old_proj)
    new_normalized = normalize_project_dict(new_proj)
    
    return old_normalized != new_normalized


# ============================================================================
# RÉGÉNÉRATION EMBEDDINGS
# ============================================================================

async def regenerate_experience_embeddings(
    db: AsyncSession, 
    experience_id: int
) -> None:
    """
    Régénère les embeddings d'une expérience.
    Met à jour embedding_status en fonction du résultat.
    """
    try:
        logger.info(f"Régénération embeddings experience {experience_id}")
        
        # Récupérer l'expérience avec projets
        result = await db.execute(
            select(Experience)
            .options(selectinload(Experience.projects))
            .where(Experience.id == experience_id)
        )
        experience = result.scalar_one_or_none()
        
        if not experience:
            logger.error(f"Experience {experience_id} introuvable")
            return
        
        # Construire le texte pour embedding (expérience + projets, aligné avec RAG)
        text_parts = [
            f"Rôle: {experience.role}",
            f"Entreprise: {experience.company}",
            f"Type de mission: {experience.mission_type}",
            f"Localisation: {experience.location}",
            f"Contexte: {experience.context}",
        ]

        # Ajouter les projets (même logique que la requête SQL RAG)
        if experience.projects:
            for project in experience.projects:
                project_parts = []
                if project.objective:
                    project_parts.append(project.objective)
                if project.problem:
                    project_parts.append(project.problem)
                if project.solution:
                    project_parts.append(project.solution)
                if project.results:
                    project_parts.append(project.results)
                if project.impact:
                    project_parts.append(project.impact)
                if project.description:
                    project_parts.append(project.description)
                if project.stack:
                    project_parts.append(f"Avec les technologies : {project.stack}")
                if project.collaborators:
                    project_parts.append(f"Travaillé avec {project.collaborators}")
                
                if project_parts:
                    text_parts.append(" ".join(project_parts))

        full_text = " ".join(text_parts)
        
        # Générer embedding
        embedding = await vectorize_query(full_text, 'voyage')
        
        # Mettre à jour en DB
        experience.embedding = embedding
        experience.embedding_status = 'done'
        await db.commit()
        
        logger.info(f"✅ Embeddings experience {experience_id} régénérés")
        
    except Exception as e:
        logger.error(f"❌ Erreur régénération embeddings experience {experience_id}: {e}")
        
        # Marquer comme failed
        result = await db.execute(
            select(Experience).where(Experience.id == experience_id)
        )
        experience = result.scalar_one_or_none()
        if experience:
            experience.embedding_status = 'failed'
            await db.commit()


async def regenerate_project_embeddings(
    db: AsyncSession, 
    project_id: int
) -> None:
    """
    Régénère les embeddings d'un projet.
    Met à jour embedding_status en fonction du résultat.
    """
    try:
        logger.info(f"Régénération embeddings project {project_id}")
        
        # Récupérer le projet
        result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        
        if not project:
            logger.error(f"Project {project_id} introuvable")
            return
        
        # Construire le texte pour embedding
        text_parts = [
            f"Projet: {project.name}",
            f"Type: {project.project_type}",
            f"Description: {project.description}",
            f"Objectif: {project.objective}",
            f"Problème: {project.problem}",
            f"Solution: {project.solution}",
            f"Résultats: {project.results}",
            f"Impact: {project.impact}",
            f"Stack: {project.stack}"
        ]
        
        if project.collaborators:
            text_parts.append(f"Collaborateurs: {project.collaborators}")
        
        full_text = " ".join(text_parts)
        
        # Générer embedding
        embedding = await vectorize_query(full_text, "voyage")
        
        # Mettre à jour en DB
        project.embedding = embedding
        project.embedding_status = 'done'
        await db.commit()
        
        logger.info(f"✅ Embeddings project {project_id} régénérés")
        
    except Exception as e:
        logger.error(f"❌ Erreur régénération embeddings project {project_id}: {e}")
        
        # Marquer comme failed
        result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if project:
            project.embedding_status = 'failed'
            await db.commit()
