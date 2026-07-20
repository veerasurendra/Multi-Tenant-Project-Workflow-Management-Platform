from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TaskAttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    uploaded_by: int
    filename: str
    uploaded_at: datetime