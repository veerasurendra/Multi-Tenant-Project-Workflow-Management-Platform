import logging
from typing import Optional

from sqlalchemy.orm import Session

from .. import models

logger = logging.getLogger(__name__)


def _notifications_enabled(db: Session, user_id: int, notification_type: Optional[str]) -> bool:
    """A notification type is enabled unless the user has an explicit opt-out row."""
    if not notification_type:
        return True

    pref = (
        db.query(models.NotificationPreference)
        .filter(
            models.NotificationPreference.user_id == user_id,
            models.NotificationPreference.notification_type == notification_type,
        )
        .first()
    )
    if pref is None:
        return True
    return pref.enabled


def create_notification(
    db: Session,
    user_id: int,
    title: str,
    message: str,
    notification_type: Optional[str] = None,
):
    try:
        if not _notifications_enabled(db, user_id, notification_type):
            return None

        notification = models.Notification(
            organization_id=db.info.get("organization_id") or db.get(models.User, user_id).organization_id,
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
        )

        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification
    except Exception as e:
        db.rollback()
        logger.exception(e)
        return None
