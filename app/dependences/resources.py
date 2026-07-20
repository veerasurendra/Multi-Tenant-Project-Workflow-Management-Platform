from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Project, Task


def get_project_or_404(db: Session, project_id: int):
    project = (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.is_deleted.is_(False),
        )
        .first()
    )

    if not project:
        raise HTTPException(404, "Project not found")

    return project


def get_task_or_404(db: Session, task_id: int):
    task = (
        db.query(Task)
        .filter(
            Task.id == task_id,
            Task.is_deleted.is_(False),
        )
        .first()
    )

    if not task:
        raise HTTPException(404, "Task not found")

    return task