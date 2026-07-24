import logging

from ..config import settings

logger = logging.getLogger(__name__)


def send_email_notification(to: str, subject: str, body: str) -> None:
    """Send an email notification.

    This is a lightweight stand-in for a real email provider (SMTP,
    SendGrid, SES, etc). When EMAIL_NOTIFICATIONS_ENABLED is False (the
    default), this simply logs what *would* have been sent, so the rest of
    the app can call it unconditionally without needing real SMTP
    credentials in dev/test environments.
    """
    if not settings.EMAIL_NOTIFICATIONS_ENABLED:
        logger.info("[email disabled] to=%s subject=%s body=%s", to, subject, body)
        return

    # Real send would go here, e.g. via smtplib or a provider SDK.
    logger.info("[email sent] to=%s subject=%s body=%s", to, subject, body)
