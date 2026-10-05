from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models import ProjectStatus

class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: ProjectStatus = ProjectStatus.planning
    start_date: datetime | None = None
    due_date: datetime | None = None

class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    status: ProjectStatus | None = None
    start_date: datetime | None = None
    due_date: datetime | None = None

class ProjectOut(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    organization_id: int
    created_by: int
    created_at: datetime
    updated_at: datetime
