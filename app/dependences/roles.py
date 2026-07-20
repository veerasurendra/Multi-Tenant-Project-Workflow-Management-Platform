from typing import Iterable

from fastapi import Depends, HTTPException, status

from ..models import RoleEnum, User
from .auth import get_current_user


def require_roles(*allowed_roles: Iterable[RoleEnum]):
    def dependency(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role.value}' is not permitted",
            )
        return current_user

    return dependency


def is_admin(user: User):
    return user.role == RoleEnum.admin


def is_manager(user: User):
    return user.role == RoleEnum.manager