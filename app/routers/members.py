from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import get_db
from app.dependences import get_current_user, get_project_or_404, ensure_can_view_project
from app.services import members as service
router = APIRouter(prefix="/projects", tags=["Project Members"])
@router.post("/{project_id}/members", response_model=schemas.ProjectMemberOut, status_code=201)
def add_project_member(project_id: int, payload: schemas.ProjectMemberCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return service.add(db, user, project_id, payload.user_id)
@router.get("/{project_id}/members", response_model=list[schemas.ProjectMemberListOut])
def list_project_members(project_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = get_project_or_404(db, project_id, user); ensure_can_view_project(db, user, row)
    rows = db.query(models.ProjectMember, models.User.full_name).join(models.User).filter(models.ProjectMember.project_id == project_id).all()
    return [{"id": m.id, "organization_id": m.organization_id, "project_id": m.project_id, "user_id": m.user_id, "added_at": m.added_at, "user_name": name} for m, name in rows]
@router.delete("/{project_id}/members/{user_id}", status_code=204)
def remove_project_member(project_id: int, user_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    service.remove(db, user, project_id, user_id)
