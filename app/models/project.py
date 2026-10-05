from __future__ import annotations

from datetime import datetime
import enum

from sqlalchemy import (
    Boolean,
    Enum as SQLEnum,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class ProjectStatus(str, enum.Enum):
    planning = "planning"
    active = "active"
    on_hold = "on_hold"
    completed = "completed"
    archived = "archived"


class Project(Base):
    __tablename__ = "projects"

    # ============================================================
    # PRIMARY KEY
    # ============================================================

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    # ============================================================
    # TENANT / ORGANIZATION
    # ============================================================

    organization_id: Mapped[int] = mapped_column(
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # ============================================================
    # PROJECT DETAILS
    # ============================================================

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
    )

    # ============================================================
    # CREATOR
    # ============================================================

    created_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    # ============================================================
    # TIMESTAMPS
    # ============================================================

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # ============================================================
    # SOFT DELETE
    # ============================================================

    status: Mapped[ProjectStatus] = mapped_column(SQLEnum(ProjectStatus), default=ProjectStatus.planning, nullable=False)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # ============================================================
    # ORGANIZATION RELATIONSHIP
    # ============================================================

    organization = relationship(
    "Organization",
    back_populates="projects",
)

    # ============================================================
    # CREATOR RELATIONSHIP
    # ============================================================

    creator = relationship(
        "User",
        back_populates="projects_created",
        foreign_keys=[created_by],
    )

    # ============================================================
    # MEMBERS
    # ============================================================

    members = relationship(
        "ProjectMember",
        back_populates="project",
        cascade="all, delete-orphan",
    )


    # ============================================================
    # TASKS
    # ============================================================

    tasks = relationship(
        "Task",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    # ============================================================
    # ACTIVITIES
    # ============================================================

    activities = relationship(
        "ActivityLog",
        primaryjoin="foreign(ActivityLog.entity_id)==Project.id",
        viewonly=True,
    )