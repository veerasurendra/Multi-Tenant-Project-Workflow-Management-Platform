from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import get_db
from app.dependences import get_current_user
from app.dependences.auth import Actor
from app.routers.organizations import MemberUpdate
from app.services.organizations import access, update_member
router = APIRouter(prefix="/admin/users", tags=["User Management"])
@router.get("", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(db, user, user.organization_id, True)
    rows = db.query(models.User, models.OrganizationMember).join(models.OrganizationMember).filter(models.OrganizationMember.organization_id == user.organization_id).all()
    return [Actor(account, user.organization, models.RoleEnum(member.role)) for account, member in rows]
@router.put("/{user_id}/role")
def change_user_role(user_id: int, role: models.RoleEnum, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = update_member(db, user, user.organization_id, user_id, MemberUpdate(role=role))
    return {"user_id": row.user_id, "role": row.role}
@router.put("/{user_id}/deactivate")
def deactivate_user(user_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    update_member(db, user, user.organization_id, user_id, MemberUpdate(is_active=False))
    return {"user_id": user_id, "is_active": False}
@router.put("/{user_id}/activate")
def activate_user(user_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    update_member(db, user, user.organization_id, user_id, MemberUpdate(is_active=True))
    return {"user_id": user_id, "is_active": True}
