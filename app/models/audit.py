from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class AuditLog(Base):
    """Field-level change history ("what changed, from what, to what, by whom").

    Distinct from ActivityLog, which records *actions* ("user did X").
    AuditLog instead records *state transitions* on a single field of an
    entity, e.g. Task.status: Pending -> In Progress.
    """

    ip_address: Mapped[str | None] = mapped_column(String(45))
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSON)

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    # ============================================================
    # TENANT / ORGANIZATION
    # ============================================================

    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    entity_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    
    # ============================================================
    # ORGANIZATION
    # ============================================================

    organization = relationship(
        "Organization",
        back_populates="audit_logs",
    )

    field_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    old_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    new_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    changed_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    changed_by_user = relationship(
        "User",
        back_populates="audit_changes",
    )
