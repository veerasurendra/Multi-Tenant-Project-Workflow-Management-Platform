from typing import List

from fastapi import APIRouter, Depends, HTTPException

from .. import models, schemas
from ..database import get_db
from ..dependences import require_roles
from sqlalchemy.orm import Session

router = APIRouter(prefix="/admin/users", tags=["User Management (Admin)"])


@router.get("", response_model=List[schemas.UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles(models.RoleEnum.admin)),
):
    return db.query(models.User).all()


@router.put("/{user_id}/role", response_model=schemas.UserOut)
def change_user_role(
    user_id: int,
    role: models.RoleEnum,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles(models.RoleEnum.admin)),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = role
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}/deactivate", response_model=schemas.UserOut)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles(models.RoleEnum.admin)),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user
