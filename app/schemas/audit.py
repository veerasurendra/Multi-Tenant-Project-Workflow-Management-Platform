from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    entity_id: int
    field_name: str
    old_value: Optional[str]
    new_value: Optional[str]
    changed_by: int
    changed_at: datetime
