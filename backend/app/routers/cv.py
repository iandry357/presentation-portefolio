from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
# from app.core.database import get_db
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

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


# Anciens endpoints (stubs pour RAG futur)
@router.get("/skills")
async def get_skills():
    """Liste des compétences (pour RAG uniquement)."""
    return {"message": "Endpoint pour RAG - à implémenter"}


@router.get("/experiences")
async def get_experiences():
    """Liste des expériences (pour RAG uniquement)."""
    return {"message": "Endpoint pour RAG - à implémenter"}


@router.get("/projects")
async def get_projects():
    """Liste des projets (pour RAG uniquement)."""
    return {"message": "Endpoint pour RAG - à implémenter"}


@router.get("/formations")
async def get_formations():
    """Liste des formations (pour RAG uniquement)."""
    return {"message": "Endpoint pour RAG - à implémenter"}