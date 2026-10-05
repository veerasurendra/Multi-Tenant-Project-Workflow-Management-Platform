from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class ProjectMember(Base):
    __tablename__ = "project_members"

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "user_id",
            name="uq_project_user",
        ),
    )

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
        Integer,
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # ============================================================
    # PROJECT
    # ============================================================

    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "projects.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    # ============================================================
    # USER
    # ============================================================

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    # ============================================================
    # TIMESTAMP
    # ============================================================

    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # ============================================================
    # ORGANIZATION RELATIONSHIP
    # ============================================================

    organization = relationship(
        "Organization",
        back_populates="project_members",
    )

    # ============================================================
    # PROJECT RELATIONSHIP
    # ============================================================

    project = relationship(
        "Project",
        back_populates="members",
    )

    # ============================================================
    # USER RELATIONSHIP
    # ============================================================

    user = relationship(
        "User",
        back_populates="memberships",
    )