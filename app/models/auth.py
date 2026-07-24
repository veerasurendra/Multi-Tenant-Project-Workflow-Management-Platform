from __future__ import annotations

from datetime import datetime
import enum

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class RoleEnum(str, enum.Enum):
    admin = "admin"
    manager = "manager"
    member = "member"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[RoleEnum] = mapped_column(
        SQLEnum(RoleEnum), default=RoleEnum.member, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    projects_created = relationship(
        "Project",
        back_populates="creator",
        foreign_keys="Project.created_by",
    )

    memberships = relationship(
        "ProjectMember",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    tasks_assigned = relationship(
        "Task",
        back_populates="assignee",
        foreign_keys="Task.assigned_to",
    )
    activities = relationship(
    "ActivityLog",
    back_populates="user",
    cascade="all, delete-orphan",
    )
    notifications = relationship(
    "Notification",
    back_populates="user",
    cascade="all, delete-orphan",
    )
    notification_preferences = relationship(
    "NotificationPreference",
    back_populates="user",
    cascade="all, delete-orphan",
    )
    refresh_tokens = relationship(
    "RefreshToken",
    back_populates="user",
    cascade="all, delete-orphan",
    )
    audit_changes = relationship(
    "AuditLog",
    back_populates="changed_by_user",
    )