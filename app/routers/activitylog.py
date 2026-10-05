import csv
import io
from datetime import datetime
from typing import Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..dependences import (
    ensure_can_view_project,
    get_current_user,
    get_project_or_404,
    is_admin,
)

router = APIRouter(
    prefix="/activities",
    tags=["Activity Logs"],
)


def _apply_filters(
    query,
    date_from: Optional[datetime],
    date_to: Optional[datetime],
    action: Optional[str],
    entity_type: Optional[str],
):
    if date_from:
        query = query.filter(models.ActivityLog.created_at >= date_from)
    if date_to:
        query = query.filter(models.ActivityLog.created_at <= date_to)
    if action:
        query = query.filter(models.ActivityLog.action == action)
    if entity_type:
        query = query.filter(models.ActivityLog.entity_type == entity_type)
    return query


@router.get("", response_model=schemas.Page[schemas.ActivityLogOut])
def all_activities(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    date_from: Optional[datetime] = Query(None, description="Filter: created_at >= this timestamp"),
    date_to: Optional[datetime] = Query(None, description="Filter: created_at <= this timestamp"),
    action: Optional[str] = Query(None, description="Filter by action type, e.g. TASK_CREATED"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type, e.g. Task, Project"),
    user_id: Optional[int] = Query(None, description="Filter by acting user (admin only)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    """Platform-wide activity feed. Admin only.

    Non-admins should use /activities/user/{id} or /activities/project/{id}
    instead, which are scoped to what they're allowed to see.
    """
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="Only admins can view the full activity feed")

    query = db.query(models.ActivityLog).filter(True if current_user.role == models.RoleEnum.super_admin and current_user.organization_id is None else models.ActivityLog.organization_id == current_user.organization_id)
    query = _apply_filters(query, date_from, date_to, action, entity_type)
    if user_id:
        query = query.filter(models.ActivityLog.user_id == user_id)

    total = query.count()
    items = (
        query.order_by(models.ActivityLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return schemas.Page(total=total, page=page, page_size=page_size, items=items)


@router.get("/user/{user_id}", response_model=schemas.Page[schemas.ActivityLogOut])
def user_activities(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    """A single user's activity history. Users may view their own; admins may view anyone's."""
    current_user_id = int(cast(int, current_user.id))
    if not is_admin(current_user) and current_user_id != user_id:
        raise HTTPException(status_code=403, detail="You can only view your own activity history")

    query = db.query(models.ActivityLog).filter(True if current_user.role == models.RoleEnum.super_admin and current_user.organization_id is None else models.ActivityLog.organization_id == current_user.organization_id).filter(models.ActivityLog.user_id == user_id)
    query = _apply_filters(query, date_from, date_to, action, entity_type)

    total = query.count()
    items = (
        query.order_by(models.ActivityLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return schemas.Page(total=total, page=page, page_size=page_size, items=items)


@router.get("/project/{project_id}", response_model=schemas.Page[schemas.ActivityLogOut])
def project_activities(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    action: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    """All activity tied to a project: the project itself plus its tasks."""
    project = get_project_or_404(
    db,
    project_id,
    current_user,
)
    ensure_can_view_project(db, current_user, project)

    task_ids = [
        row[0]
        for row in db.query(models.Task.id).filter(models.Task.project_id == project_id).all()
    ]

    query = db.query(models.ActivityLog).filter(True if current_user.role == models.RoleEnum.super_admin and current_user.organization_id is None else models.ActivityLog.organization_id == current_user.organization_id).filter(
        (
            (models.ActivityLog.entity_type == "Project")
            & (models.ActivityLog.entity_id == project_id)
        )
        | (
            (models.ActivityLog.entity_type == "Task")
            & (models.ActivityLog.entity_id.in_(task_ids))
        )
    )
    query = _apply_filters(query, date_from, date_to, action, None)

    total = query.count()
    items = (
        query.order_by(models.ActivityLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return schemas.Page(total=total, page=page, page_size=page_size, items=items)


@router.get("/export/csv")
def export_activities_csv(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
):
    """Admin-only CSV export of the full activity log, respecting the same filters as GET /activities."""
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="Only admins can export the activity log")

    query = db.query(models.ActivityLog).filter(True if current_user.role == models.RoleEnum.super_admin and current_user.organization_id is None else models.ActivityLog.organization_id == current_user.organization_id)
    query = _apply_filters(query, date_from, date_to, action, entity_type)
    rows = query.order_by(models.ActivityLog.created_at.desc()).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "user_id", "action", "entity_type", "entity_id", "description", "created_at"])
    for row in rows:
        writer.writerow(
            [row.id, row.user_id, row.action, row.entity_type, row.entity_id, row.description, row.created_at]
        )
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=activity_logs.csv"},
    )
