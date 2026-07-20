from typing import Any, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..dependencies import (
    ensure_can_manage_project,
    ensure_can_view_project,
    get_current_user,
    get_project_or_404,
    is_admin,
)
from ..utils.logging import log_activity

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("", response_model=schemas.ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: schemas.ProjectCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    current_user_id = int(cast(int, current_user.id))
    # Only Admins and Managers may create projects.
    if current_user.role not in (models.RoleEnum.admin, models.RoleEnum.manager):
        raise HTTPException(
            status_code=403, detail="Only Admins or Managers may create projects"
        )

    project = models.Project(
        name=payload.name,
        description=payload.description,
        created_by=current_user_id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    log_activity(
        db, current_user_id, "create", "Project", int(cast(int, project.id))
    )
    return project


@router.get("", response_model=schemas.Page[schemas.ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    name: Optional[str] = Query(None, description="Filter by name (partial match)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    query = db.query(models.Project).filter(models.Project.is_deleted.is_(False))

    if not is_admin(current_user):
        current_user_id = int(cast(int, current_user.id))
        member_project_ids = (
            db.query(models.ProjectMember.project_id)
            .filter(models.ProjectMember.user_id == current_user_id)
            .scalar_subquery()
        )
        query = query.filter(
            (models.Project.created_by == current_user_id)
            | (models.Project.id.in_(member_project_ids))
        )

    if name:
        query = query.filter(models.Project.name.ilike(f"%{name}%"))

    total = query.count()
    items = (
        query.order_by(models.Project.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return schemas.Page(total=total, page=page, page_size=page_size, items=items)


@router.get("/{project_id}", response_model=schemas.ProjectOut)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = get_project_or_404(db, project_id)
    ensure_can_view_project(db, current_user, project)
    return project


@router.put("/{project_id}", response_model=schemas.ProjectOut)
def update_project(
    project_id: int,
    payload: schemas.ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    current_user_id = int(cast(int, current_user.id))
    project = get_project_or_404(db, project_id)
    ensure_can_manage_project(db, current_user, project)

    if payload.name is not None:
        project.name = payload.name
    if payload.description is not None:
        project.description = payload.description

    db.commit()
    db.refresh(project)
    log_activity(
        db, current_user_id, "update", "Project", int(cast(int, project.id))
    )
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    current_user_id = int(cast(int, current_user.id))
    project = get_project_or_404(db, project_id)
    # Only Admins may delete projects, per the role matrix.
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="Only Admins may delete projects")

    project.is_deleted = True
    db.commit()
    log_activity(
        db, current_user_id, "delete", "Project", int(cast(int, project.id))
    )
    return None
