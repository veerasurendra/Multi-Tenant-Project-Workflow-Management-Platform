from typing import List, cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..dependencies import (
    ensure_can_manage_project,
    ensure_can_view_project,
    get_current_user,
    get_project_or_404,
)
from ..utils.logging import log_activity

router = APIRouter(prefix="/projects", tags=["Project Members"])


@router.post(
    "/{project_id}/members",
    response_model=schemas.ProjectMemberOut,
    status_code=status.HTTP_201_CREATED,
)
def add_project_member(
    project_id: int,
    payload: schemas.ProjectMemberCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = get_project_or_404(db, project_id)
    # Adding members is a management action: Admins, or the Manager who owns the project.
    ensure_can_manage_project(db, current_user, project)

    user = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = (
        db.query(models.ProjectMember)
        .filter(
            models.ProjectMember.project_id == project_id,
            models.ProjectMember.user_id == payload.user_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="User is already a member of this project")

    member = models.ProjectMember(project_id=project_id, user_id=payload.user_id)
    db.add(member)
    db.commit()
    db.refresh(member)
    log_activity(
        db,
        int(cast(int, current_user.id)),
        "add_member",
        "Project",
        project_id,
        details=f"user_id={int(cast(int, user.id))}",
    )
    return member


@router.get("/{project_id}/members", response_model=List[schemas.ProjectMemberListOut])
def list_project_members(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = get_project_or_404(db, project_id)
    ensure_can_view_project(db, current_user, project)

    rows = (
        db.query(models.ProjectMember, models.User.full_name)
        .join(models.User, models.ProjectMember.user_id == models.User.id)
        .filter(models.ProjectMember.project_id == project_id)
        .all()
    )
    return [
        {
            "id": member.id,
            "project_id": member.project_id,
            "user_id": member.user_id,
            "added_at": member.added_at,
            "user_name": user_name,
        }
        for member, user_name in rows
    ]
