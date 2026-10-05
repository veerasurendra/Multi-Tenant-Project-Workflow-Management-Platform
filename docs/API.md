# API reference

Canonical base URL: `http://localhost:8000/api`. Protected requests use a bearer access token. Optional `X-Organization-ID` selects an active tenant membership.

## Endpoints

| Method | Path | Operation |
|---|---|---|
| POST | `/api/auth/signup` | Signup |
| POST | `/api/auth/register` | Signup |
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/refresh` | Refresh Access Token |
| POST | `/api/auth/logout` | Logout |
| GET | `/api/auth/me` | Read Me |
| POST | `/api/auth/change-password` | Change Password |
| POST | `/api/projects` | Create Project |
| GET | `/api/projects` | List Projects |
| GET | `/api/projects/{project_id}` | Get Project |
| PATCH | `/api/projects/{project_id}` | Update Project |
| PUT | `/api/projects/{project_id}` | Update Project |
| DELETE | `/api/projects/{project_id}` | Delete Project |
| POST | `/api/projects/{project_id}/archive` | Archive Project |
| POST | `/api/projects/{project_id}/members` | Add Project Member |
| GET | `/api/projects/{project_id}/members` | List Project Members |
| DELETE | `/api/projects/{project_id}/members/{user_id}` | Remove Project Member |
| POST | `/api/tasks` | Create Task |
| GET | `/api/tasks` | List Tasks |
| GET | `/api/tasks/{task_id}` | Get Task |
| PATCH | `/api/tasks/{task_id}` | Update Task |
| PUT | `/api/tasks/{task_id}` | Update Task |
| DELETE | `/api/tasks/{task_id}` | Delete Task |
| PATCH | `/api/tasks/{task_id}/assign` | Assign Task |
| PATCH | `/api/tasks/{task_id}/status` | Task Status |
| PATCH | `/api/tasks/{task_id}/priority` | Task Priority |
| POST | `/api/tasks/{task_id}/move` | Move Task |
| POST | `/api/tasks/{task_id}/dependencies` | Add Dependency |
| GET | `/api/tasks/{task_id}/dependencies` | List Dependencies |
| DELETE | `/api/tasks/{task_id}/dependencies/{depends_on_id}` | Remove Dependency |
| GET | `/api/admin/users` | List Users |
| PUT | `/api/admin/users/{user_id}/role` | Change User Role |
| PUT | `/api/admin/users/{user_id}/deactivate` | Deactivate User |
| PUT | `/api/admin/users/{user_id}/activate` | Activate User |
| GET | `/api/notifications` | My Notifications |
| GET | `/api/notifications/unread` | Unread Notifications |
| GET | `/api/notifications/unread/count` | Unread Notification Count |
| PUT | `/api/notifications/read-all` | Mark All Read |
| PATCH | `/api/notifications/read-all` | Mark All Read |
| PUT | `/api/notifications/{notification_id}/read` | Mark Read |
| PATCH | `/api/notifications/{notification_id}/read` | Mark Read |
| DELETE | `/api/notifications/{notification_id}` | Delete Notification |
| GET | `/api/notifications/preferences` | List Notification Preferences |
| PUT | `/api/notifications/preferences` | Update Notification Preference |
| GET | `/api/activities` | All Activities |
| GET | `/api/activities/user/{user_id}` | User Activities |
| GET | `/api/activities/project/{project_id}` | Project Activities |
| GET | `/api/activities/export/csv` | Export Activities Csv |
| GET | `/api/audit-logs` | All Audit Logs |
| GET | `/api/audit-logs/export/csv` | Export Audit Logs Csv |
| GET | `/api/audit-logs/{entity_type}/{entity_id}` | Entity Audit History |
| POST | `/api/organizations` | Create Organization |
| GET | `/api/organizations` | List Organizations |
| GET | `/api/organizations/{organization_id}` | Get Organization |
| PUT | `/api/organizations/{organization_id}` | Update Organization |
| PATCH | `/api/organizations/{organization_id}` | Update Organization |
| POST | `/api/organizations/{organization_id}/members` | Add Member |
| GET | `/api/organizations/{organization_id}/members` | List Members |
| PATCH | `/api/organizations/{organization_id}/members/{user_id}` | Update Member |
| DELETE | `/api/organizations/{organization_id}/members/{user_id}` | Remove Member |
| POST | `/api/tasks/{resource_id}/comments` | Task Add Post |
| GET | `/api/tasks/{resource_id}/comments` | Task Listing Get |
| PUT | `/api/tasks/{resource_id}/comments/{comment_id}` | Task Update Put |
| PATCH | `/api/tasks/{resource_id}/comments/{comment_id}` | Task Update Patch |
| DELETE | `/api/tasks/{resource_id}/comments/{comment_id}` | Task Delete Delete |
| POST | `/api/tasks/{resource_id}/attachments` | Task Upload Post |
| GET | `/api/tasks/{resource_id}/attachments` | Task Attachments Get |
| GET | `/api/tasks/{resource_id}/attachments/{attachment_id}/download` | Task Download Get |
| POST | `/api/projects/{resource_id}/comments` | Project Add Post |
| GET | `/api/projects/{resource_id}/comments` | Project Listing Get |
| PUT | `/api/projects/{resource_id}/comments/{comment_id}` | Project Update Put |
| PATCH | `/api/projects/{resource_id}/comments/{comment_id}` | Project Update Patch |
| DELETE | `/api/projects/{resource_id}/comments/{comment_id}` | Project Delete Delete |
| POST | `/api/projects/{resource_id}/attachments` | Project Upload Post |
| GET | `/api/projects/{resource_id}/attachments` | Project Attachments Get |
| GET | `/api/projects/{resource_id}/attachments/{attachment_id}/download` | Project Download Get |
| GET | `/api/dashboard` | Get Dashboard |
| POST | `/api/notifications/process-reminders` | Process Reminders |
| GET | `/` | Health Check |

## Workflow transitions

| Current task status | Allowed next statuses |
|---|---|
| `backlog` | `cancelled`, `todo` |
| `todo` | `backlog`, `cancelled`, `in_progress` |
| `in_progress` | `blocked`, `cancelled`, `review` |
| `blocked` | `cancelled`, `in_progress`, `todo` |
| `review` | `cancelled`, `done`, `in_progress` |
| `done` | `review` |
| `cancelled` | `backlog` |

| Current project status | Allowed next statuses |
|---|---|
| `planning` | `active`, `archived` |
| `active` | `archived`, `completed`, `on_hold` |
| `on_hold` | `active`, `archived` |
| `completed` | `active`, `archived` |
| `archived` | `planning` |

## List queries

`GET /api/tasks` supports `project_id`, `status`, `priority`, `assignee_id` (or legacy `assigned_to`), `search`, `due_from`, `due_to`, `created_from`, `created_to`, `sort_by`, `sort_order`, `page`, and `page_size`. Priorities are `low`, `medium`, `high`; legacy title-case inputs also work. Task statuses are lowercase snake_case.

`GET /api/projects` supports `search`/`name`, `status`, `sort_by`, `sort_order`, `page`, and `page_size`. Page sizes are limited to 100. List responses include `total`, `page`, `page_size`, and `items`.

Date filter values are ISO 8601 timestamps; use timezone offsets or `Z`. Sorting accepts only documented field names. Resource IDs from inaccessible tenants return 404; same-tenant project permission failures return 403.

## Errors

```json
{"success": false, "error": {"code": "CONFLICT", "message": "Invalid task status transition"}}
```

HTTP 400 invalid business input; 401 missing/invalid/expired authentication; 403 role/resource access denied; 404 absent/inaccessible resource; 409 duplicate membership, invalid transition or dependency conflict; 413 oversized upload; 422 invalid schema/parameters; 500 generic internal failure. Validation errors include sanitized locations/messages, with no submitted passwords or tokens.

## Ownership and field names

`created_by` identifies the project owner/task reporter; `assigned_to` identifies the task assignee. Project and task outputs include creation/update timestamps. Task outputs include estimated/actual hours and `completed_at` for dashboard aggregates. Attachments expose name/MIME/size/upload time; authenticated download URLs replace direct storage access.

Success responses are typed resources or page envelopes; delete endpoints return 204. Audit/activity endpoints are read-only, including CSV export. UTC is used for reminder days, dashboard due-today boundaries and recently-completed windows.
