from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import func
from app import models
from app.repositories.resources import projects, tasks

def dashboard(db, actor):
    if actor.organization_id is None: raise HTTPException(400, "Select an organization using X-Organization-ID")
    now = datetime.now(timezone.utc); today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    pq, tq = projects(db, actor), tasks(db, actor)
    open_tasks = tq.filter(models.Task.status.notin_([models.StatusEnum.done, models.StatusEnum.cancelled]))
    overdue = open_tasks.filter(models.Task.due_date < now).count()
    if actor.role in (models.RoleEnum.admin, models.RoleEnum.super_admin):
        members = db.query(models.OrganizationMember).join(models.User).filter(models.OrganizationMember.organization_id == actor.organization_id)
        return {"role": actor.role.value, "total_projects": pq.count(), "active_projects": pq.filter(models.Project.status == models.ProjectStatus.active).count(),
            "completed_projects": pq.filter(models.Project.status == models.ProjectStatus.completed).count(), "total_users": members.count(),
            "active_users": members.filter(models.OrganizationMember.is_active.is_(True), models.User.is_active.is_(True)).count(), "total_tasks": tq.count(), "overdue_tasks": overdue}
    if actor.role == models.RoleEnum.project_manager:
        pq = pq.filter(models.Project.created_by == actor.id)
        tq = tq.filter(models.Task.project_id.in_(pq.with_entities(models.Project.id).scalar_subquery()))
        open_tasks = tq.filter(models.Task.status.notin_([models.StatusEnum.done, models.StatusEnum.cancelled]))
        return {"role": actor.role.value, "my_projects": pq.count(), "open_tasks": open_tasks.count(), "completed_tasks": tq.filter(models.Task.status == models.StatusEnum.done).count(),
            "overdue_tasks": open_tasks.filter(models.Task.due_date < now).count(),
            "tasks_by_member": [{"assignee_id": uid, "count": count} for uid, count in tq.with_entities(models.Task.assigned_to, func.count(models.Task.id)).group_by(models.Task.assigned_to).all()],
            "tasks_by_priority": [{"priority": priority.value, "count": count} for priority, count in tq.with_entities(models.Task.priority, func.count(models.Task.id)).group_by(models.Task.priority).all()]}
    mine = tq.filter(models.Task.assigned_to == actor.id)
    open_mine = mine.filter(models.Task.status.notin_([models.StatusEnum.done, models.StatusEnum.cancelled]))
    return {"role": actor.role.value, "my_tasks": mine.count(), "overdue_tasks": open_mine.filter(models.Task.due_date < now).count(),
        "tasks_due_today": open_mine.filter(models.Task.due_date >= today, models.Task.due_date < today+timedelta(days=1)).count(),
        "recently_completed_tasks": mine.filter(models.Task.status == models.StatusEnum.done, models.Task.completed_at >= now-timedelta(days=7)).count()}
