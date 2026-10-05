from sqlalchemy import or_
from app import models

def projects(db, actor):
    q = db.query(models.Project).filter(models.Project.is_deleted.is_(False))
    if actor.organization_id is not None:
        q = q.filter(models.Project.organization_id == actor.organization_id)
    if actor.role not in (models.RoleEnum.admin, models.RoleEnum.super_admin):
        ids = db.query(models.ProjectMember.project_id).filter_by(user_id=actor.id, organization_id=actor.organization_id).scalar_subquery()
        q = q.filter(or_(models.Project.created_by == actor.id, models.Project.id.in_(ids)))
    return q

def tasks(db, actor):
    ids = projects(db, actor).with_entities(models.Project.id).scalar_subquery()
    return db.query(models.Task).filter(models.Task.is_deleted.is_(False), models.Task.project_id.in_(ids))

def membership(db, organization_id, user_id):
    return db.query(models.OrganizationMember).filter_by(organization_id=organization_id, user_id=user_id).first()
