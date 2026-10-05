from datetime import datetime, timezone
from fastapi import HTTPException
from app import models
from app.dependences import get_task_or_404, get_project_or_404, ensure_can_manage_tasks_in_project, ensure_can_view_project, is_admin, is_manager, is_project_creator
from app.services.workflow import validate_assignee, task_transition, editable
from app.services.events import record, audit, notify

def view(db, actor, task):
    ensure_can_view_project(db, actor, task.project)

def create(db, actor, payload):
    project = get_project_or_404(db, payload.project_id, actor)
    ensure_can_manage_tasks_in_project(db, actor, project); editable(project)
    validate_assignee(db, project, payload.assigned_to)
    if payload.status not in (models.StatusEnum.backlog, models.StatusEnum.todo):
        raise HTTPException(409, "New tasks must start in backlog or todo")
    row = models.Task(**payload.model_dump(), created_by=actor.id, organization_id=project.organization_id)
    db.add(row); db.flush()
    record(db, actor, "TASK_CREATED", "Task", row.id)
    if row.assigned_to:
        record(db, actor, "TASK_ASSIGNED", "Task", row.id, {"assignee_id": row.assigned_to})
        notify(db, row.organization_id, row.assigned_to, "task_assigned", "Task Assigned", f"Task '{row.title}' was assigned to you")
    db.commit(); db.refresh(row)
    return row

def update(db, actor, task_id, payload):
    row = get_task_or_404(db, task_id, actor)
    # Serialize state and graph checks with dependency writes.
    db.query(models.Project).filter_by(id=row.project_id).with_for_update().first()
    db.refresh(row)
    project = row.project; editable(project)
    if row.is_deleted: raise HTTPException(404, "Task not found")
    data = payload.model_dump(exclude_unset=True)
    manager = is_admin(actor) or (is_manager(actor) and is_project_creator(actor, project))
    if not manager:
        if actor.role == models.RoleEnum.viewer or row.assigned_to != actor.id or set(data) - {"status", "actual_hours"}:
            raise HTTPException(403, "Members may only update status and actual hours on their assigned tasks")
    for field in ("title", "status", "priority", "project_id"):
        if field in data and data[field] is None:
            raise HTTPException(422, f"{field} cannot be null")
    destination = project
    if data.get("project_id", row.project_id) != row.project_id:
        destination = get_project_or_404(db, data["project_id"], actor)
        ensure_can_manage_tasks_in_project(db, actor, project)
        ensure_can_manage_tasks_in_project(db, actor, destination); editable(destination)
        if destination.organization_id != row.organization_id:
            raise HTTPException(403, "Tasks cannot move between organizations")
        edge = db.query(models.TaskDependency).filter((models.TaskDependency.task_id == row.id) | (models.TaskDependency.depends_on_id == row.id)).first()
        if edge:
            raise HTTPException(409, "Remove dependencies before moving the task")
    validate_assignee(db, destination, data.get("assigned_to", row.assigned_to))
    if "status" in data:
        task_transition(db, row, data["status"])
    before = {key: getattr(row, key) for key in data}
    for key, value in data.items():
        setattr(row, key, value)
    audit(db, actor, "Task", row.id, before, data)
    record(db, actor, "TASK_UPDATED", "Task", row.id)
    if "assigned_to" in data and before["assigned_to"] != row.assigned_to:
        record(db, actor, "TASK_REASSIGNED", "Task", row.id, {"old": before["assigned_to"], "new": row.assigned_to})
        if row.assigned_to:
            notify(db, row.organization_id, row.assigned_to, "task_reassigned", "Task Reassigned", f"Task '{row.title}' was assigned to you")
    if "status" in data and before["status"] != row.status:
        record(db, actor, "TASK_STATUS_CHANGED", "Task", row.id, {"status": row.status.value})
        for recipient in {row.created_by, row.assigned_to} - {None, actor.id}:
            notify(db, row.organization_id, recipient, "task_status_changed", "Task Status Changed", f"Task '{row.title}' is now {row.status.value}")
        if row.status == models.StatusEnum.done:
            notify(db, row.organization_id, row.created_by, "task_completed", "Task Completed", f"Task '{row.title}' was completed")
    if "due_date" in data and before["due_date"] != row.due_date and row.assigned_to:
        notify(db, row.organization_id, row.assigned_to, "task_deadline_updated", "Task Deadline Updated", f"Task '{row.title}' deadline changed")
    db.commit(); db.refresh(row)
    return row

def delete(db, actor, task_id):
    row = get_task_or_404(db, task_id, actor)
    db.query(models.Project).filter_by(id=row.project_id).with_for_update().first()
    db.refresh(row)
    ensure_can_manage_tasks_in_project(db, actor, row.project); editable(row.project)
    if row.is_deleted: raise HTTPException(404, "Task not found")
    if db.query(models.TaskDependency).filter_by(depends_on_id=row.id).first():
        raise HTTPException(409, "Remove dependent task links before deleting")
    row.is_deleted = True
    record(db, actor, "TASK_DELETED", "Task", row.id); db.commit()
