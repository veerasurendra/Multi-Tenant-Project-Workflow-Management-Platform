import re
from fastapi import HTTPException
from app import models
from app.repositories.resources import membership
from app.services.events import record

def access(db, actor, org_id, manage=False):
    org = db.get(models.Organization, org_id)
    if not org: raise HTTPException(404, "Organization not found")
    member = membership(db, org_id, actor.id)
    if actor.role != models.RoleEnum.super_admin and (not org.is_active or not member or not member.is_active or (manage and member.role != models.RoleEnum.admin.value)):
        raise HTTPException(403, "Organization access denied")
    return org

def create(db, actor, name):
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    if not slug: raise HTTPException(422, "Organization name must contain letters or numbers")
    if db.query(models.Organization).filter_by(slug=slug).first(): raise HTTPException(409, "Organization already exists")
    row = models.Organization(name=name.strip(), slug=slug)
    db.add(row); db.flush()
    db.add(models.OrganizationMember(organization_id=row.id, user_id=actor.id, role=models.RoleEnum.admin.value))
    record(db, actor, "ORGANIZATION_CREATED", "Organization", row.id, organization_id=row.id)
    db.commit(); db.refresh(row)
    return row

def protect_admin(db, org_id, member, new_role=None, active=None, remove=False):
    db.query(models.Organization).filter_by(id=org_id).with_for_update().first()
    losing = remove or active is False or (new_role is not None and new_role != models.RoleEnum.admin.value)
    if member.is_active and member.role == models.RoleEnum.admin.value and losing:
        count = db.query(models.OrganizationMember).filter_by(organization_id=org_id, role=models.RoleEnum.admin.value, is_active=True).count()
        if count <= 1: raise HTTPException(409, "Cannot remove or deactivate the last organization admin")

def add_member(db, actor, org_id, payload):
    access(db, actor, org_id, True)
    if payload.role == models.RoleEnum.super_admin: raise HTTPException(403, "Cannot grant super admin through organization membership")
    if payload.user_id is not None:
        user = db.get(models.User, payload.user_id)
        if not user: raise HTTPException(404, "User not found")
    else:
        from app.security import hash_password
        if not payload.email or not payload.full_name or not payload.password:
            raise HTTPException(422, "Provide user_id or full_name, email and password")
        if db.query(models.User).filter_by(email=payload.email).first(): raise HTTPException(409, "Email already exists; add the existing user by ID")
        user = models.User(email=payload.email, full_name=payload.full_name, password=hash_password(payload.password), role=payload.role, organization_id=org_id)
        db.add(user); db.flush()
    if user.role == models.RoleEnum.super_admin: raise HTTPException(400, "Global super admins do not need tenant memberships")
    if membership(db, org_id, user.id): raise HTTPException(409, "Duplicate organization membership")
    row = models.OrganizationMember(user_id=user.id, organization_id=org_id, role=payload.role.value, is_active=True)
    db.add(row); record(db, actor, "MEMBER_ADDED", "Organization", org_id, {"user_id": user.id}, org_id)
    db.commit(); db.refresh(row)
    return row

def update_member(db, actor, org_id, user_id, payload=None, remove=False):
    access(db, actor, org_id, True)
    member = db.query(models.OrganizationMember).filter_by(organization_id=org_id, user_id=user_id).with_for_update().first()
    if not member: raise HTTPException(404, "Membership not found")
    data = payload.model_dump(exclude_unset=True) if payload else {}
    if data.get("role") == models.RoleEnum.super_admin: raise HTTPException(403, "Cannot grant super admin")
    if any(value is None for value in data.values()): raise HTTPException(422, "Membership fields cannot be null")
    role = data.get("role"); role = role.value if role else None
    protect_admin(db, org_id, member, role, data.get("is_active"), remove)
    if remove or data.get("is_active") is False or role == models.RoleEnum.viewer.value:
        assigned = db.query(models.Task).filter_by(organization_id=org_id, assigned_to=user_id, is_deleted=False).first()
        if assigned: raise HTTPException(409, "Unassign this user's tasks before removing, deactivating or changing to viewer")
    if remove:
        db.query(models.ProjectMember).filter_by(organization_id=org_id, user_id=user_id).delete()
        db.delete(member)
    else:
        if role: member.role = role
        if "is_active" in data: member.is_active = data["is_active"]
    record(db, actor, "MEMBER_REMOVED" if remove else "MEMBER_UPDATED", "Organization", org_id, {"user_id": user_id}, org_id)
    db.commit()
    return member
