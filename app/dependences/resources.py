from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Project, Task, User
from ..models import RoleEnum


def get_project_or_404(
    db: Session,
    project_id: int,
    current_user: User,
):
    query = (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.is_deleted.is_(False),
        )
    )

    if current_user.role != RoleEnum.super_admin:
        query = query.filter(
            Project.organization_id == current_user.organization_id
        )

    project = query.first()

    if not project:
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        )

    return project


def get_task_or_404(
    db: Session,
    task_id: int,
    current_user: User,
):
    query = (
        db.query(Task)
        .join(Project, Task.project_id == Project.id)
        .filter(
            Project.is_deleted.is_(False),
            Task.id == task_id,
            Task.is_deleted.is_(False),
        )
    )

    if current_user.role != RoleEnum.super_admin:
        query = query.filter(
            Task.organization_id == current_user.organization_id
        )

    task = query.first()

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    return task