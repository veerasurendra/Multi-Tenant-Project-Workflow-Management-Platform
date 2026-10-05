from datetime import datetime, timedelta, timezone
from typing import cast

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .. import models, schemas
from ..schemas.auth import AccessTokenResponse, RefreshTokenRequest, LogoutRequest
from ..database import get_db
from ..config import settings
from ..dependences import get_current_user
from ..enum import ActivityAction
from ..security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
    verify_refresh_token,
)
from ..utils.logging import log_activity

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=schemas.UserOut, status_code=201)
@router.post(
    "/signup",
    response_model=schemas.UserOut,
    status_code=status.HTTP_201_CREATED,
)
def signup(
    request: Request,
    payload: schemas.UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # ============================================================
    # 1. CHECK EXISTING USER
    # ============================================================

    existing_user = (
        db.query(models.User)
        .filter(models.User.email == payload.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered",
        )

    # ============================================================
    # 2. CLEAN ORGANIZATION NAME
    # ============================================================

    organization_name = payload.organization_name.strip()

    if not organization_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization name cannot be empty",
        )

    # ============================================================
    # 3. CREATE ORGANIZATION SLUG
    # ============================================================

    organization_slug = (
        organization_name.lower()
        .strip()
        .replace(" ", "-")
        .replace("_", "-")
    )

    # ============================================================
    # 4. CHECK ORGANIZATION SLUG
    # ============================================================

    existing_organization = (
        db.query(models.Organization)
        .filter(
            models.Organization.slug == organization_slug
        )
        .first()
    )

    if existing_organization:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization already exists. Please use a different organization name.",
        )

    # ============================================================
    # 5. CREATE ORGANIZATION / TENANT
    # ============================================================

    organization = models.Organization(
        name=organization_name,
        slug=organization_slug,
        is_active=True,
    )

    db.add(organization)

    # Generate organization.id before creating user
    db.flush()

    # ============================================================
    # 6. CREATE USER
    # ============================================================

    user = models.User(
        organization_id=organization.id,
        full_name=payload.full_name,
        email=payload.email,
        password=hash_password(payload.password),
        role=models.RoleEnum.admin,
        is_active=True,
    )

    db.add(user)
    db.flush()
    db.add(models.OrganizationMember(organization_id=organization.id, user_id=user.id, role=models.RoleEnum.admin.value))

    # ============================================================
    # 7. COMMIT
    # ============================================================

    db.commit()

    db.info["ip_address"] = request.client.host if request.client else None
    db.info["organization_id"] = organization.id
    db.refresh(organization)
    db.refresh(user)

    # ============================================================
    # 8. ACTIVITY LOG
    # ============================================================

    user_id = int(cast(int, user.id))

    background_tasks.add_task(
        log_activity,
        db=db,
        user_id=user_id,
        action=ActivityAction.SIGNUP.value,
        entity_type="User",
        entity_id=user_id,
        description=(
            f"User '{user.full_name}' signed up "
            f"and created organization '{organization.name}'"
        ),
    )

    # ============================================================
    # 9. EXPLICIT RESPONSE
    # ============================================================

    return schemas.UserOut(
        id=user.id,
        organization_id=user.organization_id,
        organization_name=organization.name,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post("/login", response_model=schemas.Token)
def login(
    request: Request,
    background_tasks: BackgroundTasks,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = (
        db.query(models.User)
        .filter(models.User.email == form_data.username)
        .first()
    )

    if not user or not verify_password(
        form_data.password,
        cast(str, user.password),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not cast(bool, user.is_active):
        raise HTTPException(
            status_code=403,
            detail="User account is inactive",
        )

    login_organization_id = user.organization_id
    if user.role != models.RoleEnum.super_admin:
        member = db.query(models.OrganizationMember).join(models.Organization).filter(models.OrganizationMember.user_id == user.id, models.OrganizationMember.is_active.is_(True), models.Organization.is_active.is_(True)).order_by((models.OrganizationMember.organization_id == user.organization_id).desc(), models.OrganizationMember.id).first()
        if not member:
            raise HTTPException(403, "No active organization membership")
        login_organization_id = member.organization_id
    db.info["ip_address"] = request.client.host if request.client else None
    db.info["organization_id"] = login_organization_id

    # -----------------------
    # Create Access Token
    # -----------------------

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "role": user.role.value,
            "organization_id": user.organization_id,
        }
    )

    # -----------------------
    # Create Refresh Token
    # -----------------------

    refresh_token = create_refresh_token(
        data={
            "sub": str(user.id),
        }
    )

    # -----------------------
    # Save Refresh Token
    # -----------------------

    refresh_token_db = models.RefreshToken(
    token=hash_refresh_token(refresh_token),
    user_id=user.id,
    expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(refresh_token_db)
    db.commit()

    # -----------------------
    # Activity Log
    # -----------------------

    user_id = int(cast(int, user.id))

    background_tasks.add_task(
        log_activity,
        db=db,
        user_id=user_id,
        action=ActivityAction.LOGIN.value,
        entity_type="User",
        entity_id=user_id,
        description=f"User '{user.full_name}' logged in",
    )

    return schemas.Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )
@router.post("/refresh", response_model=schemas.Token)
def refresh_access_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    from ..services.auth import rotate_tokens
    return rotate_tokens(db, payload.refresh_token)

@router.post("/logout")
def logout(
    payload: LogoutRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    refresh_token = None

    stored_tokens = (
        db.query(models.RefreshToken)
        .filter(
            models.RefreshToken.user_id == current_user.id,
        )
        .all()
    )

    for token in stored_tokens:
        if verify_refresh_token(
            payload.refresh_token,
            token.token,
        ):
            refresh_token = token
            break

    if refresh_token:
        db.delete(refresh_token)
        db.commit()

    current_user_id = int(cast(int, current_user.id))

    background_tasks.add_task(
        log_activity,
        db=db,
        user_id=current_user_id,
        action=ActivityAction.LOGOUT.value,
        entity_type="User",
        entity_id=current_user_id,
        description=f"User '{current_user.full_name}' logged out",
    )

    return {
        "message": "Logged out successfully"
    }

@router.get("/me", response_model=schemas.UserOut)
def read_me(current_user: models.User = Depends(get_current_user)):
    return current_user

from pydantic import BaseModel, Field
class ChangePassword(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=72)

@router.post("/change-password")
def change_password(payload: ChangePassword, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not verify_password(payload.current_password, user.password):
        raise HTTPException(400, "Current password is incorrect")
    user.user.password = hash_password(payload.new_password)
    db.query(models.RefreshToken).filter_by(user_id=user.id).delete()
    db.commit()
    return {"message": "Password changed; refresh tokens revoked"}
