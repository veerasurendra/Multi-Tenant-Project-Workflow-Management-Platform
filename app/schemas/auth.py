from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from ..models import RoleEnum


class UserCreate(BaseModel):

    organization_name: str = Field(
        ...,
        min_length=1,
        max_length=120,
    )

    full_name: str = Field(
        ...,
        min_length=1,
        max_length=120,
    )

    email: EmailStr

    password: str = Field(
        ...,
        min_length=8,
        max_length=72,
    )

    #role: RoleEnum = RoleEnum.viewer

    #organization_id: Optional[int] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: Optional[int]
    organization_name: Optional[str] = None
    full_name: str
    email: EmailStr
    role: RoleEnum
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[int] = None
