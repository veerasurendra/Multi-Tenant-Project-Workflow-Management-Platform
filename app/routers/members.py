from typing import List, cast

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.utils.notification import create_notification

from .. import models, schemas
from ..database import get_db
from ..dependences import (
    ensure_can_manage_project,
    ensure_can_view_project,
    get_current_user,
    get_project_or_404,
)
from ..enum import ActivityAction
from ..utils.audit import log_change
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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    current_user_id = int(cast(int, current_user.id))
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

    background_tasks.add_task(
        create_notification,
        db=db,
        user_id=member.user_id,
        title="Added to Project",
        message=f"You have been added to project '{project.name}'.",
        notification_type=models.NotificationType.project_member_added.value,
    )

    background_tasks.add_task(
        log_activity,
        db=db,
        user_id=current_user_id,
        action=ActivityAction.MEMBER_ADDED.value,
        entity_type="Project",
        entity_id=project.id,
        description=f"Added user {member.user_id} to project '{project.name}'",
    )

    background_tasks.add_task(
        log_change,
        db=db,
        entity_type="Project",
        entity_id=project.id,
        field_name="members",
        old_value=None,
        new_value=f"+{member.user_id}",
        changed_by=current_user_id,
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
