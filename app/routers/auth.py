from datetime import datetime, timedelta, timezone
from typing import cast

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .. import models, schemas
from ..schemas.auth import AccessTokenResponse, RefreshTokenRequest, LogoutRequest
from ..database import get_db
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


@router.post("/signup", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def signup(
    payload: schemas.UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email is already registered")

    user = models.User(
        full_name=payload.full_name,
        email=payload.email,
        password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = int(cast(int, user.id))
    background_tasks.add_task(
        log_activity,
        db=db,
        user_id=user_id,
        action=ActivityAction.SIGNUP.value,
        entity_type="User",
        entity_id=user_id,
        description=f"User '{user.full_name}' signed up",
    )
    return user


@router.post("/login", response_model=schemas.Token)
def login(
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

    # -----------------------
    # Create Access Token
    # -----------------------

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "role": user.role.value,
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
    expires_at=datetime.now(timezone.utc) + timedelta(days=7),
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
@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
)
def refresh_access_token(
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    # --------------------------------
    # Decode Refresh Token
    # --------------------------------

    token_payload = decode_refresh_token(
        payload.refresh_token,
    )

    if token_payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user_id = token_payload.get("sub")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # --------------------------------
    # Check Token Exists in Database
    # --------------------------------

    refresh_token = None

    stored_tokens = (
        db.query(models.RefreshToken)
        .all()
    )

    for token in stored_tokens:
        if verify_refresh_token(
            payload.refresh_token,  # pyright: ignore[reportUndefinedVariable]
            token.token,
        ):
            refresh_token = token
            break

    if refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found",
        )

    # --------------------------------
    # Check Expiry
    # --------------------------------

    if refresh_token.expires_at < datetime.now(timezone.utc):
        db.delete(refresh_token)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )

    # --------------------------------
    # Check User
    # --------------------------------

    user = (
        db.query(models.User)
        .filter(
            models.User.id == int(user_id),
        )
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # --------------------------------
    # Generate New Access Token
    # --------------------------------

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "role": user.role.value,
        }
    )

    return AccessTokenResponse(
        access_token=access_token,
        token_type="bearer",
    )

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
