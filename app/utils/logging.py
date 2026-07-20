import logging
from typing import Optional

from sqlalchemy.orm import Session

from .. import models
from ..config import settings

logger = logging.getLogger("pm_api")
logging.basicConfig(level=logging.INFO)


def log_activity(
    db: Session,
    user_id: Optional[int],
    action: str,
    entity_type: str,
    entity_id: Optional[int] = None,
    details: Optional[str] = None,
) -> None:
    """Persist an audit-trail entry. Never raises; logging failures should not break requests."""
    try:
        entry = models.ActivityLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
        db.add(entry)
        db.commit()
    except Exception:  # pragma: no cover - defensive
        db.rollback()
        logger.exception("Failed to write activity log")


def send_email_notification(to_email: str, subject: str, body: str) -> None:
    """Log email notifications unless a real provider is configured."""
    if not settings.EMAIL_NOTIFICATIONS_ENABLED:
        logger.info("[email-disabled] to=%s subject=%s body=%s", to_email, subject, body)
        return
    logger.info("Sending email to=%s subject=%s", to_email, subject)
    # Real implementation would go here, e.g.:
    # smtplib.SMTP(...).sendmail(...)
