from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrganizationCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=2,
        max_length=150,
    )

    slug: str = Field(
        ...,
        min_length=2,
        max_length=150,
    )


class OrganizationOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    name: str
    slug: str
    is_active: bool
    created_at: datetime