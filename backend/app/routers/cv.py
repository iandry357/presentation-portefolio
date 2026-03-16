from fastapi import APIRouter, Depends, HTTPException, Header, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from fastapi.responses import Response
# from app.core.database import get_db
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

from fastapi import HTTPException, Header, BackgroundTasks
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from typing import List

from app.schemas.cv import (
    ExperienceCreate, ExperienceUpdate, ExperienceResponse, ExperienceListItem,
    ProjectCreate, ProjectUpdate, ProjectResponse
)
from app.models.cv import Experience, Project, ExperienceSkill
from app.services.cv_crud import (
    experiences_are_different,
    projects_are_different,
    regenerate_experience_embeddings,
    regenerate_project_embeddings,
    normalize_experience_dict,
    normalize_project_dict
)
from app.core.config import settings

router = APIRouter(prefix="/api/cv", tags=["cv"])


@router.get("/view")
async def view_cv():
    """
    Affiche le CV PDF (inline, pour iframe).
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("SELECT file_data, content_type, filename FROM cv_files LIMIT 1")
        )
        row = result.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="CV non trouvé. Utilisez upload_cv_pdf.py pour l'uploader.")
        
        file_data, content_type, filename = row
        
        return Response(
            content=bytes(file_data),
            media_type=content_type,
            headers={
                "Content-Disposition": f"inline; filename={filename}"
            }
        )


@router.get("/download")
async def download_cv():
    """
    Télécharge le CV PDF (attachment, pour bouton download).
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("SELECT file_data, content_type, filename FROM cv_files LIMIT 1")
        )
        row = result.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="CV non trouvé. Utilisez upload_cv_pdf.py pour l'uploader.")
        
        file_data, content_type, filename = row
        
        return Response(
            content=bytes(file_data),
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )


@router.get("/page/{page_number}")
async def get_cv_page_image(page_number: int):
    """
    Retourne une page du CV en PNG (pré-générée).
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("SELECT image_data FROM cv_pages WHERE page_number = :page"),
            {"page": page_number}
        )
        row = result.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Page {page_number} non trouvée")
        
        image_data = bytes(row[0])
        
        return Response(
            content=image_data,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=86400"}  # Cache 24h
        )

# Anciens endpoints (stubs pour RAG futur)
@router.get("/skills")
async def get_skills():
    """Liste des compétences (pour RAG uniquement)."""
    return {"message": "Endpoint pour RAG - à implémenter"}


# ============================================================================
# EXPERIENCES - CRUD
# ============================================================================

async def verify_cv_edit_code(
    x_cv_edit_code: str = Header(..., alias="X-CV-Edit-Code")
) -> None:
    """
    Middleware pour vérifier le code de sécurité sur les opérations d'écriture.
    Lève une exception 403 si le code est invalide.
    """
    if x_cv_edit_code != settings.cv_edit_secret_code:
        raise HTTPException(
            status_code=403,
            detail="Code de sécurité invalide"
        )

@router.get("/experiences", response_model=List[ExperienceListItem])
async def list_experiences(db: AsyncSession = Depends(get_db)):
    """
    Liste toutes les expériences (publique).
    Triées par date de fin décroissante (plus récent en premier).
    """
    result = await db.execute(
        select(Experience)
        .options(selectinload(Experience.projects))
        .order_by(Experience.end_date.desc().nullsfirst())
    )
    experiences = result.scalars().all()
    
    # Convertir en ExperienceListItem avec project_count
    items = []
    for exp in experiences:
        items.append(ExperienceListItem(
            id=exp.id,
            company=exp.company,
            role=exp.role,
            start_date=exp.start_date,
            end_date=exp.end_date,
            location=exp.location,
            is_stage=exp.is_stage,
            embedding_status=exp.embedding_status,
            project_count=len(exp.projects)
        ))
    
    return items


@router.get("/experiences/{experience_id}", response_model=ExperienceResponse)
async def get_experience(
    experience_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Détail d'une expérience avec projets et compétences (publique).
    """
    result = await db.execute(
        select(Experience)
        .options(
            selectinload(Experience.projects),
            selectinload(Experience.skills)
        )
        .where(Experience.id == experience_id)
    )
    experience = result.scalar_one_or_none()
    
    if not experience:
        raise HTTPException(status_code=404, detail="Expérience introuvable")
    
    return experience


@router.post("/experiences", response_model=ExperienceResponse)
async def create_experience(
    experience_data: ExperienceCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_cv_edit_code)
):
    """
    Créer une nouvelle expérience avec projets et compétences.
    Nécessite le code de sécurité.
    """
    # Créer l'expérience
    new_experience = Experience(
        company=experience_data.company,
        role=experience_data.role,
        mission_type=experience_data.mission_type,
        location=experience_data.location,
        start_date=experience_data.start_date,
        end_date=experience_data.end_date,
        duration_months=experience_data.duration_months,
        context=experience_data.context,
        is_stage=experience_data.is_stage,
        embedding_status='pending'
    )
    
    db.add(new_experience)
    await db.flush()  # Pour obtenir l'ID
    
    # Ajouter les projets
    for project_data in experience_data.projects:
        new_project = Project(
            experience_id=new_experience.id,
            name=project_data.name,
            project_type=project_data.project_type,
            description=project_data.description,
            objective=project_data.objective,
            problem=project_data.problem,
            solution=project_data.solution,
            results=project_data.results,
            impact=project_data.impact,
            stack=project_data.stack,
            collaborators=project_data.collaborators,
            start_date=project_data.start_date,
            end_date=project_data.end_date,
            duration_months=project_data.duration_months,
            embedding_status='pending'
        )
        db.add(new_project)
    
    await db.flush()  # Pour obtenir les IDs projets
    
    # Ajouter les compétences
    for skill_id in experience_data.skill_ids:
        db.add(ExperienceSkill(
            experience_id=new_experience.id,
            skill_id=skill_id
        ))
    
    await db.commit()
    
    # Régénération embeddings en arrière-plan
    background_tasks.add_task(regenerate_experience_embeddings, db, new_experience.id)
    
    # Régénérer embeddings des projets
    result = await db.execute(
        select(Project).where(Project.experience_id == new_experience.id)
    )
    projects = result.scalars().all()
    for project in projects:
        background_tasks.add_task(regenerate_project_embeddings, db, project.id)
    
    # Recharger pour retourner la réponse complète
    await db.refresh(new_experience)
    result = await db.execute(
        select(Experience)
        .options(
            selectinload(Experience.projects),
            selectinload(Experience.skills)
        )
        .where(Experience.id == new_experience.id)
    )
    
    return result.scalar_one()


@router.put("/experiences/{experience_id}", response_model=ExperienceResponse)
async def update_experience(
    experience_id: int,
    experience_data: ExperienceUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_cv_edit_code)
):
    """
    Modifier une expérience existante.
    Régénère les embeddings uniquement si des changements significatifs sont détectés.
    Nécessite le code de sécurité.
    """
    # Récupérer l'expérience existante
    result = await db.execute(
        select(Experience)
        .options(
            selectinload(Experience.projects),
            selectinload(Experience.skills)
        )
        .where(Experience.id == experience_id)
    )
    experience = result.scalar_one_or_none()
    
    if not experience:
        raise HTTPException(status_code=404, detail="Expérience introuvable")
    
    # Construire ancien dict pour comparaison
    old_exp_dict = {
        'company': experience.company,
        'role': experience.role,
        'mission_type': experience.mission_type,
        'location': experience.location,
        'start_date': experience.start_date,
        'end_date': experience.end_date,
        'context': experience.context,
        'is_stage': experience.is_stage,
        'skill_ids': [s.id for s in experience.skills],
        'projects': []
    }
    
    # Construire nouveau dict
    new_exp_dict = experience_data.dict(exclude_unset=True)
    
    # Remplir avec valeurs actuelles si non fournies
    for key in ['company', 'role', 'mission_type', 'location', 'start_date', 'end_date', 'context', 'is_stage']:
        if key not in new_exp_dict:
            new_exp_dict[key] = old_exp_dict[key]
    
    if 'skill_ids' not in new_exp_dict:
        new_exp_dict['skill_ids'] = old_exp_dict['skill_ids']
    
    # Vérifier si l'expérience a changé
    exp_changed = experiences_are_different(old_exp_dict, new_exp_dict)
    
    # Mettre à jour les champs de l'expérience
    if experience_data.company is not None:
        experience.company = experience_data.company
    if experience_data.role is not None:
        experience.role = experience_data.role
    if experience_data.mission_type is not None:
        experience.mission_type = experience_data.mission_type
    if experience_data.location is not None:
        experience.location = experience_data.location
    if experience_data.start_date is not None:
        experience.start_date = experience_data.start_date
    if experience_data.end_date is not None:
        experience.end_date = experience_data.end_date
    if experience_data.duration_months is not None:
        experience.duration_months = experience_data.duration_months
    if experience_data.context is not None:
        experience.context = experience_data.context
    if experience_data.is_stage is not None:
        experience.is_stage = experience_data.is_stage
    
    # Mettre à jour les compétences si changées
    if experience_data.skill_ids is not None:
        # Supprimer anciennes relations
        await db.execute(
            delete(ExperienceSkill).where(ExperienceSkill.experience_id == experience_id)
        )
        # Ajouter nouvelles
        for skill_id in experience_data.skill_ids:
            db.add(ExperienceSkill(
                experience_id=experience_id,
                skill_id=skill_id
            ))
    
    # Gérer les projets
    projects_changed_ids = []
    
    if experience_data.projects is not None:
        # Récupérer IDs existants
        existing_project_ids = {p.id for p in experience.projects}
        incoming_project_ids = {p.id for p in experience_data.projects if p.id}
        
        # Supprimer projets retirés
        to_delete = existing_project_ids - incoming_project_ids
        if to_delete:
            await db.execute(
                delete(Project).where(Project.id.in_(to_delete))
            )
        
        # Modifier ou créer projets
        for project_data in experience_data.projects:
            if project_data.id:
                # Modification
                result_proj = await db.execute(
                    select(Project).where(Project.id == project_data.id)
                )
                project = result_proj.scalar_one_or_none()
                
                if project:
                    # Construire dicts pour comparaison
                    old_proj_dict = {
                        'name': project.name,
                        'project_type': project.project_type,
                        'description': project.description,
                        'objective': project.objective,
                        'problem': project.problem,
                        'solution': project.solution,
                        'results': project.results,
                        'impact': project.impact,
                        'stack': project.stack,
                        'collaborators': project.collaborators,
                        'start_date': project.start_date,
                        'end_date': project.end_date
                    }
                    
                    new_proj_dict = project_data.dict(exclude_unset=True, exclude={'id'})
                    
                    # Remplir valeurs non fournies
                    for key in old_proj_dict.keys():
                        if key not in new_proj_dict:
                            new_proj_dict[key] = old_proj_dict[key]
                    
                    # Vérifier si changé
                    if projects_are_different(old_proj_dict, new_proj_dict):
                        # Mettre à jour
                        for key, value in new_proj_dict.items():
                            setattr(project, key, value)
                        project.embedding_status = 'pending'
                        projects_changed_ids.append(project.id)
            else:
                # Création
                new_project = Project(
                    experience_id=experience_id,
                    name=project_data.name,
                    project_type=project_data.project_type,
                    description=project_data.description,
                    objective=project_data.objective,
                    problem=project_data.problem,
                    solution=project_data.solution,
                    results=project_data.results,
                    impact=project_data.impact,
                    stack=project_data.stack,
                    collaborators=project_data.collaborators,
                    start_date=project_data.start_date,
                    end_date=project_data.end_date,
                    duration_months=project_data.duration_months,
                    embedding_status='pending'
                )
                db.add(new_project)
                await db.flush()
                projects_changed_ids.append(new_project.id)
    
    # Si expérience changée, régénérer embedding
    if exp_changed:
        experience.embedding_status = 'pending'
        background_tasks.add_task(regenerate_experience_embeddings, db, experience_id)
    
    # Régénérer embeddings des projets modifiés/ajoutés
    for project_id in projects_changed_ids:
        background_tasks.add_task(regenerate_project_embeddings, db, project_id)
    
    await db.commit()
    
    # Recharger pour retourner la réponse complète
    result = await db.execute(
        select(Experience)
        .options(
            selectinload(Experience.projects),
            selectinload(Experience.skills)
        )
        .where(Experience.id == experience_id)
    )
    
    return result.scalar_one()


@router.delete("/experiences/{experience_id}")
async def delete_experience(
    experience_id: int,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_cv_edit_code)
):
    """
    Supprimer une expérience (avec projets et relations en cascade).
    Nécessite le code de sécurité.
    """
    result = await db.execute(
        select(Experience).where(Experience.id == experience_id)
    )
    experience = result.scalar_one_or_none()
    
    if not experience:
        raise HTTPException(status_code=404, detail="Expérience introuvable")
    
    await db.delete(experience)
    await db.commit()
    
    return {"message": "Expérience supprimée avec succès"}


@router.post("/experiences/{experience_id}/retry-embeddings")
async def retry_experience_embeddings(
    experience_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_cv_edit_code)
):
    """
    Réessayer la génération d'embeddings en cas d'échec.
    Nécessite le code de sécurité.
    """
    result = await db.execute(
        select(Experience).where(Experience.id == experience_id)
    )
    experience = result.scalar_one_or_none()
    
    if not experience:
        raise HTTPException(status_code=404, detail="Expérience introuvable")
    
    # Marquer comme pending et relancer
    experience.embedding_status = 'pending'
    await db.commit()
    
    background_tasks.add_task(regenerate_experience_embeddings, db, experience_id)
    
    return {"message": "Régénération des embeddings lancée"}


@router.get("/projects")
async def get_projects():
    """Liste des projets (pour RAG uniquement)."""
    return {"message": "Endpoint pour RAG - à implémenter"}


@router.get("/formations")
async def get_formations():
    """Liste des formations (pour RAG uniquement)."""
    return {"message": "Endpoint pour RAG - à implémenter"}