from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import (
    Project,
    ProjectMember,
    RoleEnum,
    User,
)
from .roles import is_admin, is_manager


def is_project_creator(
    user: User,
    project: Project,
) -> bool:
    return (
        project.created_by == user.id
        and project.organization_id == user.organization_id
    )


def is_project_member(
    db: Session,
    user: User,
    project: Project,
) -> bool:
    if user.organization_id is None:
        return False

    return (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == user.id,
            ProjectMember.organization_id == user.organization_id,
        )
        .first()
        is not None
    )


def ensure_can_view_project(
    db: Session,
    user: User,
    project: Project,
):
    # Super admin is global
    if user.role == RoleEnum.super_admin:
        return

    # Tenant isolation
    if project.organization_id != user.organization_id:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this project",
        )

    if is_admin(user):
        return

    if is_project_creator(user, project):
        return

    if is_project_member(db, user, project):
        return

    raise HTTPException(
        status_code=403,
        detail="You do not have access to this project",
    )


def ensure_can_manage_project(
    db: Session,
    user: User,
    project: Project,
):
    if user.role == RoleEnum.super_admin:
        return

    if project.organization_id != user.organization_id:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to manage this project",
        )

    if is_admin(user):
        return

    if is_manager(user) and is_project_creator(user, project):
        return

    raise HTTPException(
        status_code=403,
        detail="You do not have permission to manage this project",
    )


def ensure_can_manage_tasks_in_project(
    db: Session,
    user: User,
    project: Project,
):
    if user.role == RoleEnum.super_admin:
        return

    if project.organization_id != user.organization_id:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to manage this project's tasks",
        )

    if is_admin(user):
        return

    if is_manager(user) and is_project_creator(user, project):
        return

    raise HTTPException(
        status_code=403,
        detail=(
            "Only organization admins or the project manager "
            "who owns this project can manage its tasks"
        ),
    )