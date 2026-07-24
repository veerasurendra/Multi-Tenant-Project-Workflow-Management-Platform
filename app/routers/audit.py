import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..dependences import (
    ensure_can_view_project,
    get_current_user,
    get_project_or_404,
    get_task_or_404,
    is_admin,
)

router = APIRouter(
    prefix="/audit-logs",
    tags=["Audit Logs"],
)


@router.get("", response_model=schemas.Page[schemas.AuditLogOut])
def all_audit_logs(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    entity_type: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    changed_by: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    """Full audit trail across all entities. Admin only."""
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="Only admins can view the full audit trail")

    query = db.query(models.AuditLog)
    if entity_type:
        query = query.filter(models.AuditLog.entity_type == entity_type)
    if date_from:
        query = query.filter(models.AuditLog.changed_at >= date_from)
    if date_to:
        query = query.filter(models.AuditLog.changed_at <= date_to)
    if changed_by:
        query = query.filter(models.AuditLog.changed_by == changed_by)

    total = query.count()
    items = (
        query.order_by(models.AuditLog.changed_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return schemas.Page(total=total, page=page, page_size=page_size, items=items)


@router.get("/export/csv")
def export_audit_logs_csv(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    entity_type: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
):
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="Only admins can export the audit trail")

    query = db.query(models.AuditLog)
    if entity_type:
        query = query.filter(models.AuditLog.entity_type == entity_type)
    if date_from:
        query = query.filter(models.AuditLog.changed_at >= date_from)
    if date_to:
        query = query.filter(models.AuditLog.changed_at <= date_to)

    rows = query.order_by(models.AuditLog.changed_at.desc()).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["id", "entity_type", "entity_id", "field_name", "old_value", "new_value", "changed_by", "changed_at"]
    )
    for row in rows:
        writer.writerow(
            [
                row.id,
                row.entity_type,
                row.entity_id,
                row.field_name,
                row.old_value,
                row.new_value,
                row.changed_by,
                row.changed_at,
            ]
        )
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
    )


@router.get("/{entity_type}/{entity_id}", response_model=schemas.Page[schemas.AuditLogOut])
def entity_audit_history(
    entity_type: str,
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Full change history for one specific entity, e.g. /audit-logs/Task/12.

    Access mirrors normal viewing permissions for that entity type: a
    Project's or Task's audit trail is visible to anyone who can view the
    project/task itself.
    """
    normalized = entity_type.strip().lower()

    if normalized == "project":
        project = get_project_or_404(db, entity_id)
        ensure_can_view_project(db, current_user, project)
    elif normalized == "task":
        task = get_task_or_404(db, entity_id)
        ensure_can_view_project(db, current_user, task.project)
    elif not is_admin(current_user):
        raise HTTPException(status_code=403, detail="Only admins can view this entity's audit trail")

    query = db.query(models.AuditLog).filter(
        models.AuditLog.entity_type == entity_type,
        models.AuditLog.entity_id == entity_id,
    )

    total = query.count()
    items = (
        query.order_by(models.AuditLog.changed_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return schemas.Page(total=total, page=page, page_size=page_size, items=items)
