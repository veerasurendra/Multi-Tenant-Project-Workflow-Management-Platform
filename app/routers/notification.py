from typing import List, cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..dependences import get_current_user

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)


def _own_notification_or_404(
    db: Session, current_user: models.User, notification_id: int
) -> models.Notification:
    notification = (
        db.query(models.Notification)
        .filter(
            models.Notification.id == notification_id,
            models.Notification.user_id == current_user.id,
            models.Notification.is_deleted.is_(False),
        )
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


@router.get("", response_model=List[schemas.NotificationOut])
def my_notifications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Notification)
        .filter(
            models.Notification.user_id == current_user.id,
            models.Notification.is_deleted.is_(False),
        )
        .order_by(models.Notification.created_at.desc())
        .all()
    )


@router.get("/unread", response_model=List[schemas.NotificationOut])
def unread_notifications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Notification)
        .filter(
            models.Notification.user_id == current_user.id,
            models.Notification.is_deleted.is_(False),
            models.Notification.is_read.is_(False),
        )
        .order_by(models.Notification.created_at.desc())
        .all()
    )


@router.get("/unread/count", response_model=schemas.UnreadCountOut)
def unread_notification_count(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    count = (
        db.query(models.Notification)
        .filter(
            models.Notification.user_id == current_user.id,
            models.Notification.is_deleted.is_(False),
            models.Notification.is_read.is_(False),
        )
        .count()
    )
    return schemas.UnreadCountOut(unread_count=count)


@router.put("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    updated = (
        db.query(models.Notification)
        .filter(
            models.Notification.user_id == current_user.id,
            models.Notification.is_deleted.is_(False),
            models.Notification.is_read.is_(False),
        )
        .update({models.Notification.is_read: True}, synchronize_session=False)
    )
    db.commit()
    return {"message": "All notifications marked as read", "updated_count": updated}


@router.put("/{notification_id}/read", response_model=schemas.NotificationOut)
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    notification = _own_notification_or_404(db, current_user, notification_id)
    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    notification = _own_notification_or_404(db, current_user, notification_id)
    # Soft delete: keep the historical record, just hide it from the user's view.
    notification.is_deleted = True
    db.commit()
    return None


# ---------- Notification Preferences ----------


@router.get("/preferences", response_model=List[schemas.NotificationPreferenceOut])
def list_notification_preferences(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Returns every notification type with its effective enabled state.

    Types without an explicit row are enabled by default.
    """
    current_user_id = int(cast(int, current_user.id))
    overrides = {
        pref.notification_type: pref.enabled
        for pref in db.query(models.NotificationPreference)
        .filter(models.NotificationPreference.user_id == current_user_id)
        .all()
    }
    return [
        schemas.NotificationPreferenceOut(
            notification_type=nt.value,
            enabled=overrides.get(nt.value, True),
        )
        for nt in models.NotificationType
    ]


@router.put("/preferences", response_model=schemas.NotificationPreferenceOut)
def update_notification_preference(
    payload: schemas.NotificationPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    valid_types = {nt.value for nt in models.NotificationType}
    if payload.notification_type not in valid_types:
        raise HTTPException(status_code=400, detail="Unknown notification_type")

    current_user_id = int(cast(int, current_user.id))
    pref = (
        db.query(models.NotificationPreference)
        .filter(
            models.NotificationPreference.user_id == current_user_id,
            models.NotificationPreference.notification_type == payload.notification_type,
        )
        .first()
    )
    if pref is None:
        pref = models.NotificationPreference(
            user_id=current_user_id,
            notification_type=payload.notification_type,
            enabled=payload.enabled,
        )
        db.add(pref)
    else:
        pref.enabled = payload.enabled

    db.commit()
    db.refresh(pref)
    return schemas.NotificationPreferenceOut(
        notification_type=pref.notification_type,
        enabled=pref.enabled,
    )
