import enum
import logging

from sqlalchemy.orm import Session

from .. import models

logger = logging.getLogger(__name__)


def _stringify(value):
    if value is None:
        return None
    if isinstance(value, enum.Enum):
        return str(value.value)
    return str(value)


def log_change(
    db: Session,
    entity_type: str,
    entity_id: int,
    field_name: str,
    old_value,
    new_value,
    changed_by: int,
) -> None:
    """Record a single field-level change in the audit trail.

    No-ops (does not write a row) when old_value == new_value, since an
    audit trail should only capture actual transitions.
    Values are stringified so the same column can hold text, numbers,
    enums, dates, and None uniformly. Enum members are stored as their
    `.value` (e.g. "Completed") rather than their Python repr.
    """
    if old_value == new_value:
        return

    try:
        entry = models.AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field_name,
            old_value=_stringify(old_value),
            new_value=_stringify(new_value),
            changed_by=changed_by,
        )
        db.add(entry)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception(e)


def log_field_changes(
    db: Session,
    entity_type: str,
    entity_id: int,
    changed_by: int,
    changes: dict,
) -> None:
    """Convenience wrapper to log several (field_name -> (old, new)) pairs at once."""
    for field_name, (old_value, new_value) in changes.items():
        log_change(
            db=db,
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            changed_by=changed_by,
        )
