from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ActivityLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ip_address: str | None = None
    event_metadata: dict | None = None
    id: int
    organization_id: int | None
    user_id: int
    action: str
    entity_type: str
    entity_id: Optional[int]
    description: Optional[str]
    created_at: datetime
