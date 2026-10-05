from fastapi import HTTPException
from app import models
from app.dependences import ensure_can_manage_project, get_project_or_404
from app.services.workflow import dates, project_transition
from app.services.events import record, audit, notify

def create(db, actor, payload):
    if actor.role not in (models.RoleEnum.admin, models.RoleEnum.project_manager, models.RoleEnum.super_admin) or actor.organization_id is None:
        raise HTTPException(403, "Select an organization with project management permissions")
    if payload.status != models.ProjectStatus.planning:
        raise HTTPException(409, "New projects must start in planning")
    dates(payload.start_date, payload.due_date)
    row = models.Project(**payload.model_dump(), created_by=actor.id, organization_id=actor.organization_id)
    db.add(row); db.flush()
    db.add(models.ProjectMember(project_id=row.id, user_id=actor.id, organization_id=row.organization_id))
    record(db, actor, "PROJECT_CREATED", "Project", row.id)
    db.commit(); db.refresh(row)
    return row

def update(db, actor, project_id, payload):
    row = get_project_or_404(db, project_id, actor)
    ensure_can_manage_project(db, actor, row)
    data = payload.model_dump(exclude_unset=True)
    if data.get("name", row.name) is None:
        raise HTTPException(422, "Name cannot be null")
    if "status" in data:
        project_transition(row, data["status"])
    dates(data.get("start_date", row.start_date), data.get("due_date", row.due_date))
    before = {k: getattr(row, k) for k in data}
    for key, value in data.items():
        setattr(row, key, value)
    audit(db, actor, "Project", row.id, before, data)
    record(db, actor, "PROJECT_UPDATED", "Project", row.id)
    for member in db.query(models.ProjectMember).filter_by(project_id=row.id).all():
        if member.user_id != actor.id:
            notify(db, row.organization_id, member.user_id, "project_updated", "Project Updated", f"Project '{row.name}' was updated")
    db.commit(); db.refresh(row)
    return row
