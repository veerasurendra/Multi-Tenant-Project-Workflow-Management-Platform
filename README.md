# Multi-Tenant Project & Workflow Management API

FastAPI backend for organizations, projects, tasks, workflows, dependencies, comments, attachments, notifications, dashboards, and audit history. PostgreSQL, SQLAlchemy 2, Pydantic and Alembic are used. Frontend code is outside this repository's scope.

## Setup (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit DATABASE_URL and SECRET_KEY in .env. Create the PostgreSQL database first.
alembic upgrade head
uvicorn app.main:app --reload
```

The server is at http://localhost:8000. Interactive documentation is at `/docs`, ReDoc at `/redoc`, and the OpenAPI schema at `/openapi.json`. Canonical endpoints use `/api`; legacy unprefixed URLs remain available but are hidden from OpenAPI.

```powershell
docker compose up --build
```

Docker Compose starts PostgreSQL and applies migrations before the API starts. Configure `SECRET_KEY` in your environment. Keep uploaded files on persistent storage.

## Authentication and tenant selection

1. `POST /api/auth/register` with `full_name`, `email`, `password`, and `organization_name`. Registration creates a new organization and its first organization admin. Clients cannot choose a privileged role during registration.
2. `POST /api/auth/login` uses form fields `username` (email) and `password`. Send `Authorization: Bearer <access_token>` to protected endpoints.
3. A user can belong to several organizations with a different role in each. Set `X-Organization-ID` to select an organization. The backend checks active membership on every request. Without this header, the user's primary active organization is selected, falling back to another active membership when necessary.
4. `POST /api/auth/refresh` accepts `refresh_token` and rotates it. Reusing a consumed token returns 401. Refresh tokens are stored hashed and expire. `POST /api/auth/logout` accepts the refresh token and revokes that session's refresh token. Existing access tokens expire naturally.
5. `POST /api/auth/change-password` accepts `current_password` and `new_password`, and revokes every refresh token for the user.

Inactive accounts cannot authenticate. Removed/deactivated memberships cannot access that organization. Active memberships in other organizations remain usable.

A super admin is a global account provisioned locally, never by registration or organization role changes:

```powershell
python -m app.cli create-super-admin --email admin@example.com --name "Platform Admin"
```

Super admins can inspect resources across organizations. Select `X-Organization-ID` when creating projects, requesting a tenant dashboard, or processing that tenant's reminders.

## Authorization

| Role | Permissions |
|---|---|
| Super Admin | Global administration; tenant selection for tenant-bound creation |
| Organization Admin | Organization members, all projects/tasks in that tenant, dashboards and full tenant audit feeds |
| Project Manager | Create projects; manage projects they own, their members, tasks and dependencies |
| Team Member | Read joined projects and tasks; comment/upload files; update status and actual hours on assigned tasks |
| Viewer | Read joined projects/tasks, comments/files; cannot edit or receive assignments |

Every resource request is checked against the tenant and project permissions. Project owners are automatically added as project members. Assignments require active organization and project membership, an active account, and a non-viewer role. Unassign tasks before removing a member, deactivating membership, or changing the member to viewer. The last active organization admin cannot be removed or demoted.

## Workflow

Projects: `planning -> active`, `active -> on_hold/completed`, `on_hold -> active`, `completed -> active`. Any non-archived project can be archived; `archived -> planning` restores it. Tasks, comments, files and membership cannot be modified while archived.

Tasks: `backlog -> todo`, `todo -> in_progress`, `in_progress -> review`, `review -> done`. Blocking and returning to earlier work states are supported; see [API reference](docs/API.md) for the complete transition table. Invalid transitions return 409. Legacy task inputs `Pending`, `In Progress`, and `Completed` are accepted as aliases; responses use canonical lowercase values.

Dependencies stay within one project. Cycles and duplicates are rejected. Unfinished prerequisites block entry into in-progress/review/done. Remove dependency links before moving tasks to another project or deleting a prerequisite. Moves stay within the same organization and revalidate the assignee's destination membership.

## Comments, files, notifications and jobs

Project and task comments support add/list and author-only edit/delete. `@email-prefix` or `@full-email` mentions notify active project members. Other project participants receive comment notifications.

Uploads support UTF-8 TXT/CSV, PNG/JPEG, and non-encrypted PDF. MIME, extension, file size and parsed content are checked. Default size limit is 10 MiB. Storage names use random UUIDs. Downloads pass through authenticated resource checks. Legacy attachments have `application/octet-stream`/0 metadata until replaced; storage paths are never exposed by the new API.

Notifications cover assignment/reassignment, status changes, comments/mentions, project membership, deadlines, completion, due-soon and overdue tasks. Use `/api/notifications` and PATCH read/read-all endpoints. Notification preferences apply per user. Inboxes are scoped to the selected tenant.

Due-soon/overdue processing runs in a FastAPI lifespan background task every `REMINDER_INTERVAL_SECONDS` (3600 by default). The first scheduled run occurs after that interval. Admins can trigger `/api/notifications/process-reminders`. A unique delivery record prevents repeated reminders for the same task/user/type/UTC day. Reminders consider tasks due within 24 hours. Dashboard 'today' boundaries are UTC; recently completed means the last seven days.

Activity and field-change audit records are written in the resource transaction, with organization, user, action/entity, timestamp, IP and metadata. APIs expose read/filter/export only. Authentication activity uses the existing background task mechanism. WebSocket push and real email delivery are optional and are not enabled; the existing email helper is a logging stub.

## Validation

```powershell
python -m pytest -q
# Run the same API suite against PostgreSQL in a temporary, isolated schema:
$env:PM_TEST_POSTGRES = '1'
python -m pytest -q
Remove-Item Env:PM_TEST_POSTGRES
# Verify migrations in another temporary schema, including legacy-data upgrade:
$env:PYTHONPATH = (Get-Location).Path
python tests/verify_migrations.py
```

PostgreSQL tests require permission to create/drop their generated temporary schemas. They never migrate or clear the public schema. The default suite uses an in-memory SQLite database and temporary upload directories.

## Deliverables

- [API reference](docs/API.md) and generated Swagger/ReDoc
- [Postman collection](postman_collection.json)
- [ER diagram](docs/SCHEMA.md)
- [Architecture diagram](docs/ARCHITECTURE.md)
- `.env.example`, Alembic migrations, automated tests, Dockerfile and Docker Compose

The tenant migration preserves pre-tenant rows in a legacy organization. Its downgrade intentionally refuses to merge tenant data back into an unscoped schema. Apply `alembic upgrade head` after updating code. Back up existing data before schema upgrades as part of your normal database deployment process.
