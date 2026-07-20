from .dependences import (
    ensure_can_manage_project,
    ensure_can_manage_tasks_in_project,
    ensure_can_view_project,
    get_current_user,
    get_project_or_404,
    get_task_or_404,
    is_admin,
    is_manager,
    is_project_creator,
    is_project_member,
    oauth2_scheme,
    require_roles,
)

__all__ = [
    "ensure_can_manage_project",
    "ensure_can_manage_tasks_in_project",
    "ensure_can_view_project",
    "get_current_user",
    "get_project_or_404",
    "get_task_or_404",
    "is_admin",
    "is_manager",
    "is_project_creator",
    "is_project_member",
    "oauth2_scheme",
    "require_roles",
]
