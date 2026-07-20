from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Project, ProjectMember, User
from .roles import is_admin, is_manager


def is_project_creator(user: User, project: Project):
    return project.created_by == user.id


def is_project_member(
    db: Session,
    user_id: int,
    project_id: int,
):
    return (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
        .first()
        is not None
    )


def ensure_can_view_project(
    db: Session,
    user: User,
    project: Project,
):
    if is_admin(user):
        return

    if is_project_creator(user, project):
        return

    if is_project_member(db, user.id, project.id):
        return

    raise HTTPException(
        403,
        "You do not have access to this project",
    )


def ensure_can_manage_project(
    db: Session,
    user: User,
    project: Project,
):
    if is_admin(user):
        return

    if is_manager(user) and is_project_creator(user, project):
        return

    raise HTTPException(
        403,
        "You do not have permission to manage this project",
    )


def ensure_can_manage_tasks_in_project(
    db: Session,
    user: User,
    project: Project,
):
    if is_admin(user):
        return

    if is_manager(user) and is_project_creator(user, project):
        return

    raise HTTPException(
        403,
        "Only Admins or the Manager who owns this project can manage its tasks",
    )