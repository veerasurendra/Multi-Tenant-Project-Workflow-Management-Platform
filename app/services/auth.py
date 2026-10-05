from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from app import models, schemas
from app.config import settings
from app.security import decode_refresh_token, hash_refresh_token, create_access_token, create_refresh_token

def rotate_tokens(db, raw):
    payload = decode_refresh_token(raw)
    if not payload:
        raise HTTPException(401, "Invalid or expired refresh token")
    stored = db.query(models.RefreshToken).filter_by(token=hash_refresh_token(raw)).with_for_update().first()
    if not stored:
        raise HTTPException(401, "Refresh token has been revoked")
    expiry = stored.expires_at.replace(tzinfo=timezone.utc) if stored.expires_at.tzinfo is None else stored.expires_at
    user = stored.user
    if expiry <= datetime.now(timezone.utc) or str(user.id) != payload.get("sub"):
        raise HTTPException(401, "Invalid or expired refresh token")
    if not user.is_active:
        raise HTTPException(403, "User account is inactive")
    if user.role != models.RoleEnum.super_admin:
        member = db.query(models.OrganizationMember).join(models.Organization).filter(models.OrganizationMember.user_id == user.id, models.OrganizationMember.is_active.is_(True), models.Organization.is_active.is_(True)).first()
        if not member:
            raise HTTPException(403, "Organization membership is inactive")
    access = create_access_token({"sub": str(user.id)})
    refresh = create_refresh_token({"sub": str(user.id)})
    db.delete(stored)
    db.add(models.RefreshToken(user_id=user.id, token=hash_refresh_token(refresh), expires_at=datetime.now(timezone.utc)+timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)))
    db.commit()
    return schemas.Token(access_token=access, refresh_token=refresh, token_type="bearer")
