import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.exc import IntegrityError
from app import models
from app.config import settings
from app.database import SessionLocal
from app.services.events import notify
logger = logging.getLogger(__name__)

def process(db, organization_id=None, now=None):
    now = now or datetime.now(timezone.utc)
    q = db.query(models.Task).join(models.Project).join(models.Organization, models.Project.organization_id == models.Organization.id).filter(
        models.Task.is_deleted.is_(False), models.Project.is_deleted.is_(False), models.Organization.is_active.is_(True),
        models.Project.status != models.ProjectStatus.archived, models.Task.status.notin_([models.StatusEnum.done, models.StatusEnum.cancelled]),
        models.Task.assigned_to.isnot(None), models.Task.due_date <= now+timedelta(days=1))
    if organization_id is not None: q = q.filter(models.Task.organization_id == organization_id)
    sent = 0
    for task in q.all():
        due = task.due_date.replace(tzinfo=timezone.utc) if task.due_date.tzinfo is None else task.due_date
        kind = "task_overdue" if due < now else "task_due_soon"
        key = dict(task_id=task.id, user_id=task.assigned_to, kind=kind, day=now.date().isoformat())
        if db.query(models.ReminderDelivery).filter_by(**key).first(): continue
        try:
            with db.begin_nested():
                db.add(models.ReminderDelivery(**key)); db.flush()
                notify(db, task.organization_id, task.assigned_to, kind, "Task Overdue" if due < now else "Task Due Soon", f"Task '{task.title}' is due {due.isoformat()}")
            sent += 1
        except IntegrityError:
            continue
    db.commit()
    return sent

def run_once():
    with SessionLocal() as db:
        process(db)

async def loop():
    while True:
        await asyncio.sleep(max(1, settings.REMINDER_INTERVAL_SECONDS))
        try: await asyncio.to_thread(run_once)
        except Exception: logger.exception("Scheduled reminder processing failed")
