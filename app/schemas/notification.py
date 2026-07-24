from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    message: str
    notification_type: Optional[str] = None
    is_read: bool
    created_at: datetime


class UnreadCountOut(BaseModel):
    unread_count: int


class NotificationPreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notification_type: str
    enabled: bool


class NotificationPreferenceUpdate(BaseModel):
    notification_type: str
    enabled: bool


__all__ = [
    "NotificationOut",
    "UnreadCountOut",
    "NotificationPreferenceOut",
    "NotificationPreferenceUpdate",
]