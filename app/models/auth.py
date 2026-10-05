from __future__ import annotations

from datetime import datetime
import enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class RoleEnum(str, enum.Enum):
    super_admin = "super_admin"
    admin = "organization_admin"
    project_manager = "project_manager"
    team_member = "team_member"
    viewer = "viewer"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    full_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    role: Mapped[RoleEnum] = mapped_column(
        SQLEnum(
            RoleEnum,
            values_callable=lambda enum_class: [
                item.value for item in enum_class
            ],
        ),
        default=RoleEnum.viewer,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ============================================================
    # ORGANIZATION
    # ============================================================

    organization = relationship(
        "Organization",
        back_populates="users",
    )

    # ============================================================
    # PROJECTS
    # ============================================================

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

    # ============================================================
    # TASKS
    # ============================================================

    tasks_assigned = relationship(
        "Task",
        back_populates="assignee",
        foreign_keys="Task.assigned_to",
    )

    # ============================================================
    # ACTIVITY
    # ============================================================

    activities = relationship(
        "ActivityLog",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # ============================================================
    # NOTIFICATIONS
    # ============================================================

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

    # ============================================================
    # REFRESH TOKENS
    # ============================================================

    refresh_tokens = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # ============================================================
    # AUDIT
    # ============================================================

    audit_changes = relationship(
        "AuditLog",
        back_populates="changed_by_user",
    )