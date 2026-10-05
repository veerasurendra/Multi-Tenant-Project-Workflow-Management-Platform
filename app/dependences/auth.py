from fastapi import Depends, HTTPException, Header, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, RoleEnum, OrganizationMember, Organization
from app.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

class Actor:
    """Request-scoped identity; tenant selection never mutates the user row."""
    def __init__(self, user, organization, role):
        self.user = user
        self.organization = organization
        self.organization_id = organization.id if organization else None
        self.organization_name = organization.name if organization else None
        self.role = role
    def __getattr__(self, key):
        return getattr(self.user, key)

def get_current_user(request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db), x_organization_id: int | None = Header(None)):
    payload = decode_access_token(token)
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError, KeyError):
        raise HTTPException(401, "Could not validate credentials")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(401, "User not found")
    if not user.is_active:
        raise HTTPException(403, "User account is inactive")
    org_id = x_organization_id if x_organization_id is not None else user.organization_id
    if x_organization_id is None and user.role != RoleEnum.super_admin:
        active = db.query(OrganizationMember).join(Organization).filter(OrganizationMember.user_id == user.id, OrganizationMember.is_active.is_(True), Organization.is_active.is_(True)).order_by((OrganizationMember.organization_id == user.organization_id).desc(), OrganizationMember.id).first()
        org_id = active.organization_id if active else org_id
    org = db.get(Organization, org_id) if org_id is not None else None
    role = user.role
    if user.role != RoleEnum.super_admin:
        membership = db.query(OrganizationMember).filter_by(user_id=user.id, organization_id=org_id).first()
        if not membership or not membership.is_active:
            raise HTTPException(403, "Organization membership is inactive or unavailable")
        role = RoleEnum(membership.role)
        if not org or not org.is_active:
            raise HTTPException(403, "Organization is inactive")
    elif org_id is not None and not org:
        raise HTTPException(404, "Organization not found")
    db.info.update(organization_id=org_id, ip_address=request.client.host if request.client else None)
    return Actor(user, org, role)
