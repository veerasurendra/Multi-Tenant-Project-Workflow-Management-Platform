# Database Schema Diagram

Rendered automatically by GitHub when viewing this file as a Mermaid ER diagram.

```mermaid
erDiagram
    USERS ||--o{ PROJECTS : "creates"
    USERS ||--o{ PROJECT_MEMBERS : "belongs to"
    USERS ||--o{ TASKS : "created_by"
    USERS ||--o{ TASKS : "assigned_to"
    USERS ||--o{ TASK_COMMENTS : "writes"
    USERS ||--o{ TASK_ATTACHMENTS : "uploads"
    USERS ||--o{ ACTIVITY_LOGS : "performs"
    USERS ||--o{ NOTIFICATIONS : "receives"
    USERS ||--o{ NOTIFICATION_PREFERENCES : "sets"
    USERS ||--o{ AUDIT_LOGS : "changed_by"

    PROJECTS ||--o{ PROJECT_MEMBERS : "has"
    PROJECTS ||--o{ TASKS : "contains"

    TASKS ||--o{ TASK_COMMENTS : "has"
    TASKS ||--o{ TASK_ATTACHMENTS : "has"

    USERS {
        int id PK
        string full_name
        string email UK
        string password
        enum role "admin | manager | member"
        bool is_active
        datetime created_at
    }

    PROJECTS {
        int id PK
        string name
        text description
        int created_by FK
        datetime created_at
        bool is_deleted
    }

    PROJECT_MEMBERS {
        int id PK
        int project_id FK
        int user_id FK
        datetime added_at
    }

    TASKS {
        int id PK
        string title
        text description
        enum status "Pending | In Progress | Completed"
        enum priority "Low | Medium | High"
        datetime due_date
        int assigned_to FK
        int project_id FK
        int created_by FK
        datetime created_at
        bool is_deleted
    }

    TASK_COMMENTS {
        int id PK
        int task_id FK
        int user_id FK
        text comment
        datetime created_at
    }

    TASK_ATTACHMENTS {
        int id PK
        int task_id FK
        int uploaded_by FK
        string filename
        string filepath
        datetime uploaded_at
    }

    ACTIVITY_LOGS {
        int id PK
        int user_id FK
        string action
        string entity_type
        int entity_id
        text details
        datetime timestamp
    }

    NOTIFICATIONS {
        int id PK
        int user_id FK
        string title
        text message
        string notification_type
        bool is_read
        bool is_deleted
        datetime created_at
    }

    NOTIFICATION_PREFERENCES {
        int id PK
        int user_id FK
        string notification_type
        bool enabled
    }

    AUDIT_LOGS {
        int id PK
        string entity_type
        int entity_id
        string field_name
        text old_value
        text new_value
        int changed_by FK
        datetime changed_at
    }
```

## Relationship Notes

- **Users to Projects**: one-to-many via `Project.created_by`. A project always has exactly one creator.
- **Users to Projects membership**: many-to-many through `ProjectMember`, with `(project_id, user_id)` unique.
- **Projects to Tasks**: one-to-many. The API uses soft delete, while ORM cascades help with hard-delete cleanup.
- **Users to Tasks assignment**: one-to-many via nullable `Task.assigned_to`.
- **Tasks to Comments and Attachments**: one-to-many, cascade-deleted with the parent task at the ORM level.
- **ActivityLogs**: append-only audit trail using `entity_type` and `entity_id` for loose references (records *actions*, e.g. `TASK_CREATED`, `LOGIN`).
- **Notifications**: one-to-many from User; soft-deleted via `is_deleted` rather than hard-deleted, so a user's notification history survives even after they clear their inbox. `notification_type` matches the `NotificationType` enum and is used to check `NotificationPreference` opt-outs before a notification is created.
- **NotificationPreferences**: one-to-many from User, unique on `(user_id, notification_type)`. Absence of a row means the notification type defaults to enabled; a row with `enabled=false` is an explicit opt-out.
- **AuditLogs**: distinct from ActivityLogs — records *field-level state transitions* (old value -> new value) rather than actions. Loosely referenced via `entity_type`/`entity_id`, same pattern as ActivityLogs, so both Task and Project changes share one table. A row is only written when the old and new values actually differ.
