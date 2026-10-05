from app import models
from app.utils.audit import _stringify
from app.utils.notification import _notifications_enabled

def record(db, actor, action, entity, entity_id, metadata=None, organization_id=None):
    if organization_id is None and entity in {"Project", "Task"}:
        row = db.get(models.Project if entity == "Project" else models.Task, entity_id)
        organization_id = row.organization_id if row else None
    db.add(models.ActivityLog(user_id=actor.id, organization_id=organization_id or actor.organization_id,
        action=action, entity_type=entity, entity_id=entity_id, description=action.replace("_", " ").title(),
        ip_address=db.info.get("ip_address"), event_metadata=metadata or {}))

def audit(db, actor, entity, entity_id, before, after):
    row = db.get(models.Project if entity == "Project" else models.Task, entity_id)
    organization_id = row.organization_id if row else actor.organization_id
    for field, old in before.items():
        new = after[field]
        if old != new:
            db.add(models.AuditLog(organization_id=organization_id, entity_type=entity, entity_id=entity_id,
                field_name=field, old_value=_stringify(old), new_value=_stringify(new), changed_by=actor.id,
                ip_address=db.info.get("ip_address"), event_metadata={}))

def notify(db, organization_id, user_id, kind, title, message):
    notification_type = getattr(models.NotificationType, kind, None)
    kind = notification_type.value if notification_type else kind
    membership = db.query(models.OrganizationMember).filter_by(organization_id=organization_id, user_id=user_id, is_active=True).first()
    user = db.get(models.User, user_id)
    if not membership or not user or not user.is_active or not _notifications_enabled(db, user_id, kind):
        return
    db.add(models.Notification(organization_id=organization_id, user_id=user_id, title=title, message=message, notification_type=kind))
