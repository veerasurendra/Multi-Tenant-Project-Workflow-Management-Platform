from datetime import datetime, timezone
from fastapi import HTTPException
from app import models
from app.repositories.resources import membership

TASK_TRANSITIONS = {
    "backlog": {"todo", "cancelled"}, "todo": {"backlog", "in_progress", "cancelled"},
    "in_progress": {"blocked", "review", "cancelled"}, "blocked": {"todo", "in_progress", "cancelled"},
    "review": {"in_progress", "done", "cancelled"}, "done": {"review"}, "cancelled": {"backlog"}}
PROJECT_TRANSITIONS = {"planning": {"active", "archived"}, "active": {"on_hold", "completed", "archived"},
    "on_hold": {"active", "archived"}, "completed": {"active", "archived"}, "archived": {"planning"}}

def validate_assignee(db, project, user_id):
    if user_id is None:
        return
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "Assignee not found")
    member = db.query(models.OrganizationMember).filter_by(organization_id=project.organization_id, user_id=user_id).with_for_update().first()
    if not user.is_active or not member or not member.is_active:
        raise HTTPException(400, "Assignee must be an active member of this organization")
    if member.role == models.RoleEnum.viewer.value:
        raise HTTPException(400, "Viewers cannot be assigned tasks")
    project_member = db.query(models.ProjectMember).filter_by(project_id=project.id, user_id=user_id).with_for_update().first()
    if not project_member:
        raise HTTPException(400, "Assignee must belong to this project")

def task_transition(db, task, new_status):
    if new_status is None:
        raise HTTPException(422, "Status cannot be null")
    if task.status == new_status:
        return
    if new_status.value not in TASK_TRANSITIONS[task.status.value]:
        raise HTTPException(409, "Invalid task status transition")
    if new_status.value in {"in_progress", "review", "done"}:
        prerequisites = db.query(models.Task).join(models.TaskDependency, models.TaskDependency.depends_on_id == models.Task.id).filter(models.TaskDependency.task_id == task.id).all()
        if any(t.is_deleted or t.status != models.StatusEnum.done for t in prerequisites):
            raise HTTPException(409, "Task dependencies are not completed")
    task.completed_at = datetime.now(timezone.utc) if new_status == models.StatusEnum.done else None

def project_transition(project, status):
    if status is None:
        raise HTTPException(422, "Status cannot be null")
    if status != project.status and status.value not in PROJECT_TRANSITIONS[project.status.value]:
        raise HTTPException(409, "Invalid project status transition")

def dates(start, due):
    if start: start = start.replace(tzinfo=timezone.utc) if start.tzinfo is None else start
    if due: due = due.replace(tzinfo=timezone.utc) if due.tzinfo is None else due
    if start and due and start > due:
        raise HTTPException(422, "Due date must be on or after start date")

def editable(project):
    if project.status == models.ProjectStatus.archived:
        raise HTTPException(409, "Archived projects cannot be modified")

def dependency(db, task, prerequisite):
    if task.project_id != prerequisite.project_id:
        raise HTTPException(400, "Dependencies must be in the same project")
    if task.id == prerequisite.id:
        raise HTTPException(409, "Circular dependency")
    # Lock the project to serialize graph edits and prevent concurrent cycles.
    locked_project_id = task.project_id
    db.query(models.Project).filter_by(id=locked_project_id).with_for_update().first()
    db.refresh(task); db.refresh(prerequisite)
    if task.is_deleted or prerequisite.is_deleted:
        raise HTTPException(404, "Task not found")
    if task.project_id != locked_project_id or prerequisite.project_id != locked_project_id:
        raise HTTPException(409, "Task project changed; retry the dependency operation")
    edges = db.query(models.TaskDependency).join(models.Task, models.TaskDependency.task_id == models.Task.id).filter(models.Task.project_id == task.project_id).all()
    graph = {}
    for edge in edges:
        graph.setdefault(edge.task_id, []).append(edge.depends_on_id)
    if prerequisite.id in graph.get(task.id, []):
        raise HTTPException(409, "Dependency already exists")
    stack, seen = [prerequisite.id], set()
    while stack:
        current = stack.pop()
        if current == task.id:
            raise HTTPException(409, "Circular dependency")
        if current not in seen:
            seen.add(current)
            stack.extend(graph.get(current, []))
    if task.status.value in {"in_progress", "review", "done"} and prerequisite.status != models.StatusEnum.done:
        raise HTTPException(409, "Cannot add unfinished dependency to a started task")
    row = models.TaskDependency(task_id=task.id, depends_on_id=prerequisite.id)
    db.add(row)
    return row
