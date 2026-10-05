from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from app import models
from app.database import get_db
from app.dependences import get_current_user
from app.services.dashboard import dashboard
from app.services.reminders import process
router = APIRouter(tags=["Dashboard and Background Jobs"])
@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return dashboard(db, user)
@router.post("/notifications/process-reminders")
def process_reminders(db: Session = Depends(get_db), user=Depends(get_current_user)):
    if user.role not in (models.RoleEnum.admin, models.RoleEnum.super_admin) or user.organization_id is None:
        raise HTTPException(403, "Only admins in a selected organization may process reminders")
    return {"processed": process(db, user.organization_id)}
