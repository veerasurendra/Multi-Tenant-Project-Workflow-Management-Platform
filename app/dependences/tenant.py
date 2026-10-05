from fastapi import Depends, HTTPException, status

from ..models import RoleEnum, User
from .auth import get_current_user


def get_current_organization_id(
    current_user: User = Depends(get_current_user),
) -> int:
    """
    Return the authenticated user's organization ID.

    Super admins are global users and should use dedicated
    super-admin endpoints when operating across organizations.
    """

    if current_user.role == RoleEnum.super_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Super admin does not have a single organization",
        )

    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with an organization",
        )

    if (
        current_user.organization is not None
        and not current_user.organization.is_active
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization is inactive",
        )

    return current_user.organization_id