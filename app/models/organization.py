from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        index=True,
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

    users = relationship(
        "User",
        back_populates="organization",
    )

    projects = relationship(
        "Project",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    tasks = relationship(
        "Task",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    project_members = relationship(
        "ProjectMember",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    activities = relationship(
        "ActivityLog",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    notifications = relationship(
        "Notification",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    audit_logs = relationship(
            "AuditLog",
            back_populates="organization",
            cascade="all, delete-orphan",
    )