import logging

from sqlalchemy.orm import Session

from .. import models

logger = logging.getLogger(__name__)


def log_activity(
    db: Session,
    user_id: int,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    description: str | None = None,
):
    try:
        activity = models.ActivityLog(
            ip_address=db.info.get("ip_address"),
            event_metadata={},
            organization_id=db.info.get("organization_id") or db.get(models.User, user_id).organization_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
        )

        db.add(activity)
        db.commit()

    except Exception as e:
        db.rollback()
        logger.exception(e)
