import re
from fastapi import HTTPException
from app import models
from app.dependences import get_project_or_404, get_task_or_404, ensure_can_view_project
from app.services.workflow import editable
from app.services.events import record, notify

def resource(db, actor, kind, resource_id, write=False):
    row = get_task_or_404(db, resource_id, actor) if kind == "task" else get_project_or_404(db, resource_id, actor)
    project = row.project if kind == "task" else row
    ensure_can_view_project(db, actor, project)
    if write:
        if actor.role == models.RoleEnum.viewer: raise HTTPException(403, "Viewers cannot modify comments or files")
        editable(project)
    return row, project

def comments_model(kind):
    return models.TaskComment if kind == "task" else models.ProjectComment

def add_comment(db, actor, kind, resource_id, text):
    row, project = resource(db, actor, kind, resource_id, True)
    cls = comments_model(kind)
    comment = cls(**{f"{kind}_id": resource_id}, user_id=actor.id, comment=text)
    db.add(comment); db.flush()
    record(db, actor, "COMMENT_ADDED", kind.title(), resource_id, {"comment_id": comment.id})
    recipients = {m.user_id for m in db.query(models.ProjectMember).filter_by(project_id=project.id).all()}
    recipients.add(project.created_by)
    mentions = set(re.findall(r"@([A-Za-z0-9_.+-]+(?:@[A-Za-z0-9.-]+\.[A-Za-z]{2,})?)", text))
    for user_id in recipients - {actor.id}:
        user = db.get(models.User, user_id)
        mentioned = user.email in mentions or user.email.split("@")[0] in mentions
        notify(db, project.organization_id, user_id, "user_mentioned" if mentioned else "comment_added",
            "You were mentioned" if mentioned else "Comment Added", f"A comment was added to {kind} {resource_id}")
    db.commit(); db.refresh(comment)
    return comment

def modify_comment(db, actor, kind, resource_id, comment_id, text=None, delete=False):
    resource(db, actor, kind, resource_id, True)
    cls = comments_model(kind)
    row = db.query(cls).filter(cls.id == comment_id, getattr(cls, f"{kind}_id") == resource_id).first()
    if not row: raise HTTPException(404, "Comment not found")
    if row.user_id != actor.id: raise HTTPException(403, "Only the author may modify this comment")
    if delete: db.delete(row)
    else: row.comment = text
    record(db, actor, "COMMENT_DELETED" if delete else "COMMENT_UPDATED", kind.title(), resource_id, {"comment_id": comment_id})
    db.commit()
    return row
