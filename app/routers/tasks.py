import os
import shutil
import uuid
from typing import List, Optional, cast

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings
from ..database import get_db
from ..dependencies import (
    ensure_can_manage_tasks_in_project,
    get_current_user,
    get_project_or_404,
    get_task_or_404,
    is_admin,
    is_manager,
    is_project_creator,
)
from ..utils.logging import log_activity, send_email_notification

router = APIRouter(tags=["Tasks"])


def _ensure_can_view_task(db: Session, user: models.User, task: models.Task) -> None:
    if is_admin(user):
        return
    project = task.project
    if is_manager(user) and is_project_creator(user, project):
        return
    if task.assigned_to == user.id:
        return
    raise HTTPException(status_code=403, detail="You do not have access to this task")


def _get_assignee_or_404(db: Session, user_id: int) -> models.User:
    assignee = db.query(models.User).filter(models.User.id == user_id).first()
    if not assignee:
        raise HTTPException(status_code=404, detail="Assignee not found")
    if not assignee.is_active:
        raise HTTPException(status_code=400, detail="Assignee account is inactive")
    return assignee


@router.post("/tasks", response_model=schemas.TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    current_user_id = int(cast(int, current_user.id))
    project = get_project_or_404(db, payload.project_id)
    ensure_can_manage_tasks_in_project(db, current_user, project)

    if payload.assigned_to:
        _get_assignee_or_404(db, payload.assigned_to)

    task = models.Task(
        title=payload.title,
        description=payload.description,
        status=payload.status,
        priority=payload.priority,
        due_date=payload.due_date,
        assigned_to=payload.assigned_to,
        project_id=payload.project_id,
        created_by=current_user_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    log_activity(db, current_user_id, "create", "Task", int(cast(int, task.id)))

    if task.assigned_to:
        assignee = db.query(models.User).filter(models.User.id == task.assigned_to).first()
        if assignee:
            send_email_notification(
                assignee.email,
                subject=f"New task assigned: {task.title}",
                body=f"You have been assigned task '{task.title}' in project '{project.name}'.",
            )
    return task


@router.get("/tasks", response_model=schemas.Page[schemas.TaskOut])
def list_tasks(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    project_id: Optional[int] = None,
    status_filter: Optional[models.StatusEnum] = Query(None, alias="status"),
    priority: Optional[models.PriorityEnum] = None,
    assigned_to: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    query = db.query(models.Task).filter(models.Task.is_deleted.is_(False))

    if not is_admin(current_user):
        current_user_id = int(cast(int, current_user.id))
        owned_project_ids = (
            db.query(models.Project.id)
            .filter(models.Project.created_by == current_user_id)
            .scalar_subquery()
        )
        query = query.filter(
            (models.Task.assigned_to == current_user_id)
            | (models.Task.project_id.in_(owned_project_ids))
        )

    if project_id:
        query = query.filter(models.Task.project_id == project_id)
    if status_filter:
        query = query.filter(models.Task.status == status_filter)
    if priority:
        query = query.filter(models.Task.priority == priority)
    if assigned_to:
        query = query.filter(models.Task.assigned_to == assigned_to)

    total = query.count()
    items = (
        query.order_by(models.Task.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return schemas.Page(total=total, page=page, page_size=page_size, items=items)


@router.get("/tasks/{task_id}", response_model=schemas.TaskOut)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = get_task_or_404(db, task_id)
    _ensure_can_view_task(db, current_user, task)
    return task


@router.put("/tasks/{task_id}", response_model=schemas.TaskOut)
def update_task(
    task_id: int,
    payload: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    current_user_id = int(cast(int, current_user.id))
    task = get_task_or_404(db, task_id)
    project = task.project

    if is_admin(current_user) or (is_manager(current_user) and is_project_creator(current_user, project)):
        # Admins/owning-Managers can update any field, including reassignment.
        update_data = payload.model_dump(exclude_unset=True)
        reassigned = "assigned_to" in update_data and update_data["assigned_to"] != task.assigned_to
        if update_data.get("assigned_to") is not None:
            _get_assignee_or_404(db, update_data["assigned_to"])
        for field, value in update_data.items():
            setattr(task, field, value)
        db.commit()
        db.refresh(task)
        log_activity(db, current_user_id, "update", "Task", int(cast(int, task.id)))
        if reassigned and task.assigned_to:
            assignee = db.query(models.User).filter(models.User.id == task.assigned_to).first()
            if assignee:
                send_email_notification(
                    assignee.email,
                    subject=f"Task reassigned: {task.title}",
                    body=f"Task '{task.title}' has been assigned to you.",
                )
        return task

    if task.assigned_to == current_user_id:
        # Members may only change status on their own tasks.
        update_data = payload.model_dump(exclude_unset=True)
        disallowed = set(update_data.keys()) - {"status"}
        if disallowed:
            raise HTTPException(
                status_code=403,
                detail="Members may only update the status of their assigned tasks",
            )
        if "status" in update_data:
            task.status = update_data["status"]
        db.commit()
        db.refresh(task)
        log_activity(
            db, current_user_id, "update_status", "Task", int(cast(int, task.id))
        )
        return task

    raise HTTPException(status_code=403, detail="You do not have permission to update this task")


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    current_user_id = int(cast(int, current_user.id))
    task = get_task_or_404(db, task_id)
    project = task.project
    ensure_can_manage_tasks_in_project(db, current_user, project)

    task.is_deleted = True
    db.commit()
    log_activity(db, current_user_id, "delete", "Task", int(cast(int, task.id)))
    return None


# ---------- Task Comments ----------


@router.post(
    "/tasks/{task_id}/comments",
    response_model=schemas.TaskCommentOut,
    status_code=status.HTTP_201_CREATED,
)
def add_task_comment(
    task_id: int,
    payload: schemas.TaskCommentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    current_user_id = int(cast(int, current_user.id))
    task = get_task_or_404(db, task_id)
    _ensure_can_view_task(db, current_user, task)

    comment = models.TaskComment(
        task_id=task_id, user_id=current_user_id, comment=payload.comment
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    log_activity(db, current_user_id, "comment", "Task", task_id)
    return comment


@router.get("/tasks/{task_id}/comments", response_model=List[schemas.TaskCommentOut])
def list_task_comments(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    current_user_id = int(cast(int, current_user.id))
    task = get_task_or_404(db, task_id)
    _ensure_can_view_task(db, current_user, task)
    return (
        db.query(models.TaskComment)
        .filter(models.TaskComment.task_id == task_id)
        .order_by(models.TaskComment.created_at.asc())
        .all()
    )


# ---------- Task Attachments ----------


@router.post(
    "/tasks/{task_id}/attachments",
    response_model=schemas.TaskAttachmentOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_task_attachment(
    task_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    current_user_id = int(cast(int, current_user.id))
    task = get_task_or_404(db, task_id)
    _ensure_can_view_task(db, current_user, task)

    filename = os.path.basename(file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}_{filename}"
    dest_path = os.path.join(settings.UPLOAD_DIR, safe_name)
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    attachment = models.TaskAttachment(
        task_id=task_id,
        uploaded_by=current_user_id,
        filename=filename,
        filepath=dest_path,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    log_activity(db, current_user_id, "attach_file", "Task", task_id)
    return attachment


@router.get("/tasks/{task_id}/attachments", response_model=List[schemas.TaskAttachmentOut])
def list_task_attachments(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = get_task_or_404(db, task_id)
    _ensure_can_view_task(db, current_user, task)
    return (
        db.query(models.TaskAttachment).filter(models.TaskAttachment.task_id == task_id).all()
    )
