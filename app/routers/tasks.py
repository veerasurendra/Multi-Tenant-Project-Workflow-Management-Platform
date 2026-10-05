from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, case
from pydantic import BaseModel
from app import models, schemas
from app.database import get_db
from app.dependences import get_current_user, get_task_or_404, ensure_can_manage_tasks_in_project
from app.repositories.resources import tasks
from app.services import tasks as service
from app.services.workflow import dependency, editable
from app.services.events import record
router = APIRouter(tags=["Tasks"])

@router.post("/tasks", response_model=schemas.TaskOut, status_code=201)
def create_task(payload: schemas.TaskCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return service.create(db, user, payload)

@router.get("/tasks", response_model=schemas.Page[schemas.TaskOut])
def list_tasks(db: Session = Depends(get_db), user=Depends(get_current_user), project_id: int | None = None,
    status: models.StatusEnum | None = None, priority: models.PriorityEnum | None = None,
    assigned_to: int | None = None, assignee_id: int | None = None, search: str | None = None,
    due_from: datetime | None = None, due_to: datetime | None = None,
    created_from: datetime | None = None, created_to: datetime | None = None,
    sort_by: Literal["title", "created_at", "updated_at", "due_date", "priority", "status"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    q = tasks(db, user)
    for column, value in [(models.Task.project_id, project_id), (models.Task.status, status), (models.Task.priority, priority), (models.Task.assigned_to, assignee_id if assignee_id is not None else assigned_to)]:
        if value is not None:
            q = q.filter(column == value)
    if search:
        q = q.filter(or_(models.Task.title.ilike(f"%{search}%"), models.Task.description.ilike(f"%{search}%")))
    for column, low, high in [(models.Task.due_date, due_from, due_to), (models.Task.created_at, created_from, created_to)]:
        if low and high and low > high:
            raise HTTPException(422, "Invalid date filter range")
        if low: q = q.filter(column >= low)
        if high: q = q.filter(column <= high)
    total = q.count(); column = getattr(models.Task, sort_by)
    if sort_by == "priority":
        column = case((models.Task.priority == models.PriorityEnum.low, 1), (models.Task.priority == models.PriorityEnum.medium, 2), else_=3)
    elif sort_by == "status":
        column = case(*[(models.Task.status == status, rank) for rank, status in enumerate(models.StatusEnum)], else_=99)
    rows = q.order_by(column.asc() if sort_order == "asc" else column.desc(), models.Task.id).offset((page-1)*page_size).limit(page_size).all()
    return schemas.Page(total=total, page=page, page_size=page_size, items=rows)

@router.get("/tasks/{task_id}", response_model=schemas.TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = get_task_or_404(db, task_id, user); service.view(db, user, row)
    return row

@router.put("/tasks/{task_id}", response_model=schemas.TaskOut)
@router.patch("/tasks/{task_id}", response_model=schemas.TaskOut)
def update_task(task_id: int, payload: schemas.TaskUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return service.update(db, user, task_id, payload)

class Assignment(BaseModel):
    assigned_to: int | None
class Move(BaseModel):
    project_id: int
class Priority(BaseModel):
    priority: models.PriorityEnum

@router.patch("/tasks/{task_id}/assign", response_model=schemas.TaskOut)
def assign_task(task_id: int, payload: Assignment, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return service.update(db, user, task_id, schemas.TaskUpdate(assigned_to=payload.assigned_to))

@router.patch("/tasks/{task_id}/status", response_model=schemas.TaskOut)
def task_status(task_id: int, payload: schemas.TaskStatusUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return service.update(db, user, task_id, schemas.TaskUpdate(status=payload.status))

@router.patch("/tasks/{task_id}/priority", response_model=schemas.TaskOut)
def task_priority(task_id: int, payload: Priority, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return service.update(db, user, task_id, schemas.TaskUpdate(priority=payload.priority))

@router.post("/tasks/{task_id}/move", response_model=schemas.TaskOut)
def move_task(task_id: int, payload: Move, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return service.update(db, user, task_id, schemas.TaskUpdate(project_id=payload.project_id))

@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    service.delete(db, user, task_id)

class Dependency(BaseModel):
    depends_on_id: int

@router.post("/tasks/{task_id}/dependencies", status_code=201)
def add_dependency(task_id: int, payload: Dependency, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = get_task_or_404(db, task_id, user); ensure_can_manage_tasks_in_project(db, user, row.project); editable(row.project)
    prerequisite = get_task_or_404(db, payload.depends_on_id, user)
    link = dependency(db, row, prerequisite)
    record(db, user, "TASK_DEPENDENCY_ADDED", "Task", row.id)
    db.commit(); db.refresh(link)
    return {"id": link.id, "task_id": task_id, "depends_on_id": link.depends_on_id}

@router.get("/tasks/{task_id}/dependencies")
def list_dependencies(task_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = get_task_or_404(db, task_id, user); service.view(db, user, row)
    return [{"id": e.id, "task_id": e.task_id, "depends_on_id": e.depends_on_id} for e in db.query(models.TaskDependency).filter_by(task_id=task_id).all()]

@router.delete("/tasks/{task_id}/dependencies/{depends_on_id}", status_code=204)
def remove_dependency(task_id: int, depends_on_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = get_task_or_404(db, task_id, user); ensure_can_manage_tasks_in_project(db, user, row.project); editable(row.project)
    db.query(models.Project).filter_by(id=row.project_id).with_for_update().first()
    link = db.query(models.TaskDependency).filter_by(task_id=task_id, depends_on_id=depends_on_id).first()
    if not link: raise HTTPException(404, "Dependency not found")
    db.delete(link); record(db, user, "TASK_DEPENDENCY_REMOVED", "Task", row.id); db.commit()
