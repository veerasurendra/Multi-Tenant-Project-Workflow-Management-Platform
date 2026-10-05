# Database ER diagram

Generated from the SQLAlchemy models. Roles are stored as enums on accounts and tenant-specific strings on organization memberships. Comments/files inherit tenant authorization from their project or task.

```mermaid
erDiagram
    ORGANIZATIONS ||--o{ USERS : "organization_id"
    ORGANIZATIONS ||--o{ ACTIVITY_LOGS : "organization_id"
    USERS ||--o{ ACTIVITY_LOGS : "user_id"
    USERS ||--o{ AUDIT_LOGS : "changed_by"
    ORGANIZATIONS ||--o{ AUDIT_LOGS : "organization_id"
    USERS ||--o{ NOTIFICATION_PREFERENCES : "user_id"
    USERS ||--o{ NOTIFICATIONS : "user_id"
    ORGANIZATIONS ||--o{ NOTIFICATIONS : "organization_id"
    USERS ||--o{ ORGANIZATION_MEMBERS : "user_id"
    ORGANIZATIONS ||--o{ ORGANIZATION_MEMBERS : "organization_id"
    USERS ||--o{ PROJECTS : "created_by"
    ORGANIZATIONS ||--o{ PROJECTS : "organization_id"
    USERS ||--o{ REFRESH_TOKENS : "user_id"
    USERS ||--o{ PROJECT_ATTACHMENTS : "uploaded_by"
    PROJECTS ||--o{ PROJECT_ATTACHMENTS : "project_id"
    USERS ||--o{ PROJECT_COMMENTS : "user_id"
    PROJECTS ||--o{ PROJECT_COMMENTS : "project_id"
    PROJECTS ||--o{ PROJECT_MEMBERS : "project_id"
    ORGANIZATIONS ||--o{ PROJECT_MEMBERS : "organization_id"
    USERS ||--o{ PROJECT_MEMBERS : "user_id"
    USERS ||--o{ TASKS : "created_by"
    ORGANIZATIONS ||--o{ TASKS : "organization_id"
    USERS ||--o{ TASKS : "assigned_to"
    PROJECTS ||--o{ TASKS : "project_id"
    TASKS ||--o{ REMINDER_DELIVERIES : "task_id"
    USERS ||--o{ REMINDER_DELIVERIES : "user_id"
    USERS ||--o{ TASK_ATTACHMENTS : "uploaded_by"
    TASKS ||--o{ TASK_ATTACHMENTS : "task_id"
    USERS ||--o{ TASK_COMMENTS : "user_id"
    TASKS ||--o{ TASK_COMMENTS : "task_id"
    TASKS ||--o{ TASK_DEPENDENCIES : "depends_on_id"
    TASKS ||--o{ TASK_DEPENDENCIES : "task_id"
    ORGANIZATIONS {
        integer id PK
        string name
        string slug UK
        boolean is_active
        datetime created_at
    }
    USERS {
        integer id PK
        integer organization_id FK
        string full_name
        string email UK
        string password
        enum role
        boolean is_active
        datetime created_at
    }
    ACTIVITY_LOGS {
        string ip_address
        json metadata
        integer id PK
        integer user_id FK
        integer organization_id FK
        string action
        string entity_type
        integer entity_id
        text description
        datetime created_at
    }
    AUDIT_LOGS {
        string ip_address
        json metadata
        integer id PK
        integer organization_id FK
        string entity_type
        integer entity_id
        string field_name
        text old_value
        text new_value
        integer changed_by FK
        datetime changed_at
    }
    NOTIFICATION_PREFERENCES {
        integer id PK
        integer user_id FK
        string notification_type
        boolean enabled
    }
    NOTIFICATIONS {
        integer id PK
        integer user_id FK
        integer organization_id FK
        string title
        text message
        string notification_type
        boolean is_read
        boolean is_deleted
        datetime created_at
    }
    ORGANIZATION_MEMBERS {
        integer id PK
        integer organization_id FK
        integer user_id FK
        string role
        boolean is_active
        datetime created_at
    }
    PROJECTS {
        integer id PK
        integer organization_id FK
        string name
        text description
        integer created_by FK
        datetime created_at
        enum status
        datetime start_date
        datetime due_date
        datetime updated_at
        boolean is_deleted
    }
    REFRESH_TOKENS {
        integer id PK
        string token UK
        integer user_id FK
        datetime expires_at
        datetime created_at
    }
    PROJECT_ATTACHMENTS {
        integer id PK
        integer project_id FK
        integer uploaded_by FK
        string filename
        string filepath
        string mime_type
        integer file_size
        datetime uploaded_at
    }
    PROJECT_COMMENTS {
        integer id PK
        integer project_id FK
        integer user_id FK
        text comment
        datetime created_at
        datetime updated_at
    }
    PROJECT_MEMBERS {
        integer id PK
        integer organization_id FK
        integer project_id FK
        integer user_id FK
        datetime added_at
    }
    TASKS {
        integer id PK
        integer organization_id FK
        string title
        text description
        enum status
        enum priority
        datetime due_date
        integer assigned_to FK
        integer project_id FK
        integer created_by FK
        datetime created_at
        float estimated_hours
        float actual_hours
        datetime updated_at
        datetime completed_at
        boolean is_deleted
    }
    REMINDER_DELIVERIES {
        integer id PK
        integer task_id FK
        integer user_id FK
        string kind
        string day
    }
    TASK_ATTACHMENTS {
        integer id PK
        integer task_id FK
        integer uploaded_by FK
        string mime_type
        integer file_size
        string filename
        string filepath
        datetime uploaded_at
    }
    TASK_COMMENTS {
        integer id PK
        integer task_id FK
        integer user_id FK
        text comment
        datetime created_at
    }
    TASK_DEPENDENCIES {
        integer id PK
        integer task_id FK
        integer depends_on_id FK
    }
```

Organization and project memberships have unique `(organization_id, user_id)` and `(project_id, user_id)` pairs. Task dependency pairs are unique with a self-reference check. Refresh token hashes and organization slugs are unique. Reminder deliveries are unique by task/user/type/UTC day. Foreign keys and ORM cascades define cleanup; projects/tasks use soft delete through the API. Global super-admin authentication events may have no organization.
