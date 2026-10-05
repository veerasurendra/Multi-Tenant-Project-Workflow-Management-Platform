from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import get_db
from app.dependences import get_current_user, get_project_or_404, ensure_can_view_project, is_admin
from app.repositories.resources import projects
from app.services import projects as service
from app.services.events import record
router = APIRouter(prefix="/projects", tags=["Projects"])

@router.post("", response_model=schemas.ProjectOut, status_code=201)
def create_project(payload: schemas.ProjectCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return service.create(db, user, payload)

@router.get("", response_model=schemas.Page[schemas.ProjectOut])
def list_projects(db: Session = Depends(get_db), user=Depends(get_current_user), name: str | None = None,
    search: str | None = None, status: models.ProjectStatus | None = None,
    sort_by: Literal["name", "created_at", "due_date", "updated_at"] = "created_at", sort_order: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    q = projects(db, user)
    if search or name:
        q = q.filter(models.Project.name.ilike(f"%{search or name}%"))
    if status:
        q = q.filter(models.Project.status == status)
    total = q.count(); column = getattr(models.Project, sort_by)
    items = q.order_by(column.asc() if sort_order == "asc" else column.desc(), models.Project.id).offset((page-1)*page_size).limit(page_size).all()
    return schemas.Page(total=total, page=page, page_size=page_size, items=items)

@router.get("/{project_id}", response_model=schemas.ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = get_project_or_404(db, project_id, user); ensure_can_view_project(db, user, row)
    return row

@router.put("/{project_id}", response_model=schemas.ProjectOut)
@router.patch("/{project_id}", response_model=schemas.ProjectOut)
def update_project(project_id: int, payload: schemas.ProjectUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return service.update(db, user, project_id, payload)

@router.post("/{project_id}/archive", response_model=schemas.ProjectOut)
def archive_project(project_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return service.update(db, user, project_id, schemas.ProjectUpdate(status=models.ProjectStatus.archived))

@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = get_project_or_404(db, project_id, user)
    if not is_admin(user):
        raise HTTPException(403, "Only admins may delete projects")
    row.is_deleted = True
    record(db, user, "PROJECT_DELETED", "Project", row.id)
    db.commit()
