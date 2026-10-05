from fastapi import HTTPException
from app import models
from app.dependences import get_project_or_404, ensure_can_manage_project
from app.repositories.resources import membership
from app.services.workflow import editable
from app.services.events import record, notify, audit

def add(db, actor, project_id, user_id):
    project = get_project_or_404(db, project_id, actor); ensure_can_manage_project(db, actor, project); editable(project)
    user = db.get(models.User, user_id); org_member = membership(db, project.organization_id, user_id)
    if not user or not org_member or not org_member.is_active or not user.is_active:
        raise HTTPException(400, "User must be an active member of this organization")
    if db.query(models.ProjectMember).filter_by(project_id=project_id, user_id=user_id).first():
        raise HTTPException(409, "Duplicate project membership")
    row = models.ProjectMember(project_id=project_id, user_id=user_id, organization_id=project.organization_id)
    db.add(row); db.flush()
    record(db, actor, "MEMBER_ADDED", "Project", project_id, {"user_id": user_id})
    audit(db, actor, "Project", project_id, {"members": None}, {"members": f"+{user_id}"})
    notify(db, project.organization_id, user_id, "project_member_added", "Added to Project", f"You were added to '{project.name}'")
    db.commit(); db.refresh(row)
    return row

def remove(db, actor, project_id, user_id):
    project = get_project_or_404(db, project_id, actor); ensure_can_manage_project(db, actor, project); editable(project)
    if user_id == project.created_by: raise HTTPException(409, "Cannot remove the project owner")
    row = db.query(models.ProjectMember).filter_by(project_id=project_id, user_id=user_id).with_for_update().first()
    if not row: raise HTTPException(404, "Project member not found")
    if db.query(models.Task).filter_by(project_id=project_id, assigned_to=user_id, is_deleted=False).first():
        raise HTTPException(409, "Unassign this user's tasks before removing membership")
    db.delete(row)
    record(db, actor, "MEMBER_REMOVED", "Project", project_id, {"user_id": user_id})
    audit(db, actor, "Project", project_id, {"members": str(user_id)}, {"members": None})
    db.commit()
