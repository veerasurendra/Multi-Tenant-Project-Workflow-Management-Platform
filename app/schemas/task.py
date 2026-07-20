from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from ..models import PriorityEnum, StatusEnum


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    status: StatusEnum = StatusEnum.pending
    priority: PriorityEnum = PriorityEnum.medium
    due_date: Optional[datetime] = None
    assigned_to: Optional[int] = None
    project_id: int


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[StatusEnum] = None
    priority: Optional[PriorityEnum] = None
    due_date: Optional[datetime] = None
    assigned_to: Optional[int] = None


class TaskStatusUpdate(BaseModel):
    status: StatusEnum


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str]
    status: StatusEnum
    priority: PriorityEnum
    due_date: Optional[datetime]
    assigned_to: Optional[int]
    project_id: int
    created_by: int
    created_at: datetime


class TaskCommentCreate(BaseModel):
    comment: str = Field(..., min_length=1)


class TaskCommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    user_id: int
    comment: str
    created_at: datetime