# Project Management API with RBAC

A FastAPI backend for managing projects, project membership, and tasks with
three roles: **Admin**, **Manager**, and **Member**.

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
|   |-- models.py
|   |-- schemas.py
|   |-- security.py
|   |-- dependencies.py
|   |-- routers/
|   |   |-- auth.py
|   |   |-- projects.py
|   |   |-- members.py
|   |   |-- tasks.py
|   |   `-- users.py
|   `-- utils/
|       `-- logging.py
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
- **ActivityLog**: append-only audit trail.

## Extra Features

- Activity logging for auth, project, member, task, comment, and attachment actions.
- Email notification hook for task assignment and reassignment.
- Pagination and filtering for project and task lists.
- Soft deletes for projects and tasks.
- Postman collection in [postman_collection.json](postman_collection.json).
