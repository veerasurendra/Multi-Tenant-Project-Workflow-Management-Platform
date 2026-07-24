# Project Management API with RBAC + Notification & Activity Tracking

A FastAPI backend for managing projects, project membership, and tasks with
three roles: **Admin**, **Manager**, and **Member** — extended with a full
notification system, activity logging, and a field-level audit trail.

## Tech Stack

| Concern | Choice |
|---|---|
| Framework | FastAPI |
| ORM | SQLAlchemy 2.x |
| Validation | Pydantic v2 |
| Database | SQLite by default, PostgreSQL via Docker Compose |
| Migrations | Alembic |
| Auth | JWT with python-jose and bcrypt password hashing |
| Tests | Pytest with FastAPI TestClient and in-memory SQLite |
| Containerization | Docker and Docker Compose |

## Project Structure

```text
pm_api/
|-- app/
|   |-- main.py
|   |-- config.py
|   |-- database.py
|   |-- enum.py
|   |-- security.py
|   |-- models/
|   |   |-- auth.py
|   |   |-- project.py
|   |   |-- member.py
|   |   |-- task.py
|   |   |-- activity.py
|   |   |-- notification.py
|   |   `-- audit.py
|   |-- schemas/
|   |-- dependences/
|   |-- routers/
|   |   |-- auth.py
|   |   |-- projects.py
|   |   |-- members.py
|   |   |-- tasks.py
|   |   |-- users.py
|   |   |-- notification.py
|   |   |-- activitylog.py
|   |   `-- audit.py
|   `-- utils/
|       |-- logging.py
|       |-- notification.py
|       |-- audit.py
|       `-- email.py
|-- alembic/
|-- docs/
|-- tests/
|-- postman_collection.json
|-- requirements.txt
|-- Dockerfile
`-- docker-compose.yml
```

## Role-Based Access Control

| Action | Admin | Manager | Member |
|---|---|---|---|
| Create project | Yes | Yes | No |
| View all projects | Yes | No, own and member-of only | No, member-of only |
| Update project | Yes, any | Yes, own only | No |
| Delete project | Yes | No | No |
| Add project members | Yes, any project | Yes, own projects | No |
| Create, assign, or reassign task | Yes | Yes, within own projects | No |
| Update task, any field | Yes | Yes, within own projects | No |
| Update own task status | Yes | Yes | Yes |
| Delete task | Yes | Yes, within own projects | No |
| View task | Yes, any | Yes, own projects | Yes, assigned tasks only |
| Manage users | Yes | No | No |

Manager ownership means `Project.created_by == user.id`. Admins are the only
role with unrestricted project and task visibility.

## API Endpoints

### Authentication

| Method | Path | Access |
|---|---|---|
| POST | `/auth/signup` | Public |
| POST | `/auth/login` | Public OAuth2 password flow; send `username` as email |
| POST | `/auth/logout` | Authenticated; JWTs are stateless, so this just records a LOGOUT activity |
| GET | `/auth/me` | Authenticated |

### Projects

| Method | Path | Access |
|---|---|---|
| POST | `/projects` | Admin, Manager |
| GET | `/projects` | Authenticated and scoped by role; supports `?name=&page=&page_size=` |
| GET | `/projects/{id}` | Admin, creator, or project member |
| PUT | `/projects/{id}` | Admin, or Manager who created it |
| DELETE | `/projects/{id}` | Admin only, soft delete |

### Project Members

| Method | Path | Access |
|---|---|---|
| POST | `/projects/{id}/members` | Admin, or Manager who owns the project |
| GET | `/projects/{id}/members` | Admin, creator, or project member |

### Tasks

| Method | Path | Access |
|---|---|---|
| POST | `/tasks` | Admin, or Manager who owns the target project |
| GET | `/tasks` | Authenticated and scoped by role; supports `?project_id=&status=&priority=&assigned_to=&page=&page_size=` |
| GET | `/tasks/{id}` | Admin, owning Manager, or assignee |
| PUT | `/tasks/{id}` | Admin/owning Manager can update any field; assignee can update status only |
| DELETE | `/tasks/{id}` | Admin, or Manager who owns the project |
| POST | `/tasks/{id}/comments` | Anyone with task view access |
| GET | `/tasks/{id}/comments` | Anyone with task view access |
| POST | `/tasks/{id}/attachments` | Anyone with task view access |
| GET | `/tasks/{id}/attachments` | Anyone with task view access |

### Admin User Management

| Method | Path | Access |
|---|---|---|
| GET | `/admin/users` | Admin |
| PUT | `/admin/users/{id}/role?role=` | Admin |
| PUT | `/admin/users/{id}/deactivate` | Admin |

### Notifications

| Method | Path | Access |
|---|---|---|
| GET | `/notifications` | Own notifications only |
| GET | `/notifications/unread` | Own notifications only |
| GET | `/notifications/unread/count` | Own notifications only |
| PUT | `/notifications/read-all` | Own notifications only |
| PUT | `/notifications/{id}/read` | Owner only |
| DELETE | `/notifications/{id}` | Owner only; soft delete |
| GET | `/notifications/preferences` | Own preferences; types default to enabled |
| PUT | `/notifications/preferences` | Own preferences; body `{"notification_type": "TASK_ASSIGNED", "enabled": false}` |

Notifications are generated automatically for: Task Assigned, Task Reassigned,
Task Deadline Updated, Task Completed, Added to Project, and Project Updated.
Each carries a `notification_type` matching `NotificationType`; a user can
opt out of any type via the preferences endpoints, in which case that type
is silently suppressed at creation time.

### Activity Logs

| Method | Path | Access |
|---|---|---|
| GET | `/activities` | Admin only; supports `?date_from=&date_to=&action=&entity_type=&user_id=&page=&page_size=` |
| GET | `/activities/user/{id}` | Self, or Admin for anyone |
| GET | `/activities/project/{id}` | Anyone who can view the project (includes the project's own events plus all of its tasks' events) |
| GET | `/activities/export/csv` | Admin only; same filters as `/activities`, streamed as a CSV download |

Every significant action (signup, login, logout, project/task CRUD, member
added, comments, attachments, status changes, assignment) writes an
`ActivityLog` row via a FastAPI `BackgroundTask`, so the request completes
without waiting on the log write.

### Audit Logs

| Method | Path | Access |
|---|---|---|
| GET | `/audit-logs` | Admin only; supports `?entity_type=&date_from=&date_to=&changed_by=&page=&page_size=` |
| GET | `/audit-logs/{entity_type}/{entity_id}` | Anyone who can view that entity (e.g. `/audit-logs/Task/12`) |
| GET | `/audit-logs/export/csv` | Admin only; same filters as `/audit-logs` |

Audit logs are field-level, not action-level: a `Task.status` change from
`Pending` to `In Progress` becomes one row with `old_value="Pending"`,
`new_value="In Progress"`. Currently tracked: `Task.status`, `Task.priority`,
`Task.title`, `Task.description`, `Task.due_date`, `Task.assigned_to`,
`Project.name`, `Project.description`, and project membership additions.
A row is only written when the value actually changes.

## Getting Started

### Local SQLite

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

The API runs at `http://127.0.0.1:8000`. Swagger docs are available at
`http://127.0.0.1:8000/docs`.

`app/main.py` also calls `Base.metadata.create_all()` on startup as a local
convenience. For production, run Alembic migrations explicitly.

### Docker Compose

```bash
docker compose up --build
```

This starts PostgreSQL, waits for it to be healthy, runs `alembic upgrade head`,
and starts Uvicorn.

## Running Tests

```bash
pytest -v
```

The tests use an isolated in-memory SQLite database and do not touch
`pm_api.db`.

## Data Model

See [docs/SCHEMA.md](docs/SCHEMA.md) for the ER diagram.

- **User**: authentication and role data.
- **Project**: project record with soft delete.
- **ProjectMember**: many-to-many project membership join table.
- **Task**: project task with status, priority, assignee, and soft delete.
- **TaskComment**: task discussion entries.
- **TaskAttachment**: uploaded file metadata.
- **ActivityLog**: append-only log of *actions* (who did what), e.g. `TASK_CREATED`, `LOGIN`.
- **Notification**: per-user notifications with soft delete and an optional `notification_type`.
- **NotificationPreference**: per-user, per-type opt-out switch (types default to enabled).
- **AuditLog**: append-only log of *field-level changes* (old value -> new value), e.g. `Task.status: Pending -> Completed`.

## Extra Features

### Notification & Activity Tracking System

- Automatic notifications for task assignment, reassignment, deadline
  changes, completion, project updates, and being added to a project.
- Per-user notification preferences to opt out of any notification type.
- Soft-deleted notifications (kept for history, hidden from the user's inbox).
- Full activity feed with admin-wide, per-user, and per-project views, filterable
  by date range, action type, and entity type.
- Field-level audit trail for tasks (status, priority, title, description,
  due date, assignee) and projects (name, description, membership), with a
  per-entity history endpoint (`/audit-logs/{entity_type}/{entity_id}`).
- CSV export for both the activity feed and the audit trail.
- All logging/notification/email side effects run via FastAPI `BackgroundTasks`,
  so writes don't block the API response.
- Email notification hook (stubbed; logs instead of sending unless
  `EMAIL_NOTIFICATIONS_ENABLED=true`) for task assignment and deadline changes.

### Other

- Pagination and filtering for project and task lists.
- Soft deletes for projects and tasks.
- Postman collection in [postman_collection.json](postman_collection.json).
