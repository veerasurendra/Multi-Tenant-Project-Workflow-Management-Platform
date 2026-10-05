from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectMemberCreate(BaseModel):
    user_id: int


class ProjectMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    project_id: int
    user_id: int
    added_at: datetime


class ProjectMemberListOut(ProjectMemberOut):
    user_name: str
