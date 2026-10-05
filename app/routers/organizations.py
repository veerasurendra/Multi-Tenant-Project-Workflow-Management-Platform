from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from sqlalchemy.orm import Session
from datetime import datetime
from app import models
from app.database import get_db
from app.dependences import get_current_user
from app.services import organizations as service
from app.services.events import record
router = APIRouter(prefix="/organizations", tags=["Organizations"])

class OrgCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
class OrgUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    is_active: bool | None = None
class OrgOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    is_active: bool
    created_at: datetime
class MemberCreate(BaseModel):
    user_id: int | None = None
    full_name: str | None = Field(None, min_length=1, max_length=120)
    email: EmailStr | None = None
    password: str | None = Field(None, min_length=8, max_length=72)
    role: models.RoleEnum = models.RoleEnum.team_member
class MemberUpdate(BaseModel):
    role: models.RoleEnum | None = None
    is_active: bool | None = None
class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    organization_id: int
    user_id: int
    role: str
    is_active: bool

@router.post("", response_model=OrgOut, status_code=201)
def create_organization(payload: OrgCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return service.create(db, user, payload.name)
@router.get("", response_model=list[OrgOut])
def list_organizations(db: Session = Depends(get_db), user=Depends(get_current_user)):
    q = db.query(models.Organization)
    if user.role != models.RoleEnum.super_admin:
        q = q.join(models.OrganizationMember).filter(models.OrganizationMember.user_id == user.id, models.OrganizationMember.is_active.is_(True))
    return q.all()
@router.get("/{organization_id}", response_model=OrgOut)
def get_organization(organization_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return service.access(db, user, organization_id)
@router.patch("/{organization_id}", response_model=OrgOut)
@router.put("/{organization_id}", response_model=OrgOut)
def update_organization(organization_id: int, payload: OrgUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = service.access(db, user, organization_id, True)
    data = payload.model_dump(exclude_unset=True)
    if any(v is None for v in data.values()): raise HTTPException(422, "Fields cannot be null")
    for key, value in data.items(): setattr(row, key, value)
    record(db, user, "ORGANIZATION_UPDATED", "Organization", row.id, organization_id=row.id)
    db.commit(); db.refresh(row)
    return row
@router.post("/{organization_id}/members", response_model=MemberOut, status_code=201)
def add_member(organization_id: int, payload: MemberCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return service.add_member(db, user, organization_id, payload)
@router.get("/{organization_id}/members", response_model=list[MemberOut])
def list_members(organization_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    service.access(db, user, organization_id)
    return db.query(models.OrganizationMember).filter_by(organization_id=organization_id).all()
@router.patch("/{organization_id}/members/{user_id}", response_model=MemberOut)
def update_member(organization_id: int, user_id: int, payload: MemberUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return service.update_member(db, user, organization_id, user_id, payload)
@router.delete("/{organization_id}/members/{user_id}", status_code=204)
def remove_member(organization_id: int, user_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    service.update_member(db, user, organization_id, user_id, remove=True)
