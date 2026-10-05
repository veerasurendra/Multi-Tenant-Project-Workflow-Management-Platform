from __future__ import annotations

from datetime import datetime
import enum

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, Boolean, Float, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class StatusEnum(str, enum.Enum):
    backlog = "backlog"
    todo = "todo"
    in_progress = "in_progress"
    blocked = "blocked"
    review = "review"
    done = "done"
    cancelled = "cancelled"
    pending = "todo"
    completed = "done"

    @classmethod
    def _missing_(cls, value):
        return {"Pending": cls.todo, "In Progress": cls.in_progress, "Completed": cls.done}.get(value)


class PriorityEnum(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"

    @classmethod
    def _missing_(cls, value):
        return {"Low": cls.low, "Medium": cls.medium, "High": cls.high}.get(value)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

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
    
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(Text)

    status: Mapped[StatusEnum] = mapped_column(
        SQLEnum(StatusEnum),
        default=StatusEnum.pending,
    )

    priority: Mapped[PriorityEnum] = mapped_column(
        SQLEnum(PriorityEnum),
        default=PriorityEnum.medium,
    )

    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    assigned_to: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id"),
    )

    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("projects.id"),
    )

    
    # ============================================================
    # ORGANIZATION
    # ============================================================

    organization = relationship(
        "Organization",
        back_populates="tasks",
    )
 
    created_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    estimated_hours: Mapped[float | None] = mapped_column(Float)
    actual_hours: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    project = relationship(
        "Project",
        back_populates="tasks",
    )

    assignee = relationship(
        "User",
        back_populates="tasks_assigned",
        foreign_keys=[assigned_to],
    )

    comments = relationship(
        "TaskComment",
        back_populates="task",
        cascade="all, delete-orphan",
    )

    attachments = relationship(
        "TaskAttachment",
        back_populates="task",
        cascade="all, delete-orphan",
    )


class TaskComment(Base):
    __tablename__ = "task_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    task_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tasks.id"),
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
    )

    comment: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    task = relationship(
        "Task",
        back_populates="comments",
    )

    user = relationship("User")


class TaskAttachment(Base):
    __tablename__ = "task_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    task_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tasks.id"),
    )

    uploaded_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
    )

    mime_type: Mapped[str] = mapped_column(String(100), default="application/octet-stream")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    filename: Mapped[str] = mapped_column(String(255))

    filepath: Mapped[str] = mapped_column(String(500))

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    task = relationship(
        "Task",
        back_populates="attachments",
    )