from fastapi import Depends, HTTPException, status

from ..models import RoleEnum, User
from .auth import get_current_user


def require_roles(*allowed_roles: RoleEnum):
    def dependency(current_user: User = Depends(get_current_user)):
        role = getattr(current_user, "role", None)
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{getattr(role, 'value', role)}' is not permitted",
            )
        return current_user

    return dependency


def is_admin(user: User):
    return user.role in (RoleEnum.admin, RoleEnum.super_admin)


def is_manager(user: User):
    return user.role == RoleEnum.project_manager