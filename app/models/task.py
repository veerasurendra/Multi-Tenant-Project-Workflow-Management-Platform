from __future__ import annotations

from datetime import datetime
import enum

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class StatusEnum(str, enum.Enum):
    pending = "Pending"
    in_progress = "In Progress"
    completed = "Completed"


class PriorityEnum(str, enum.Enum):
    low = "Low"
    medium = "Medium"
    high = "High"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

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

    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    assigned_to: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id"),
    )

    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("projects.id"),
    )

    created_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

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