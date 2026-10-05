# Backend architecture

```mermaid
flowchart TD
    Client[API client / frontend] --> Routes[FastAPI routes / Pydantic validation]
    Routes --> Auth[JWT and request-scoped tenant / role dependencies]
    Auth --> Services[Business services]
    Services --> Repos[Tenant-scoped repositories]
    Repos --> ORM[SQLAlchemy models]
    ORM --> DB[(PostgreSQL)]
    Services --> Events[Transactional notifications / activity / audit]
    Events --> DB
    Worker[FastAPI lifespan reminder worker] --> Services
    Routes --> Storage[Validated private file storage]
    Alembic[Alembic schema migrations] --> DB
```

`app/routers` defines HTTP contracts; `app/dependences` resolves the authenticated account, active organization and role, and resource permissions. `app/services` owns workflow, assignment, dependency, organization/member, comment, file and dashboard rules. `app/repositories` builds scoped queries. `app/models` defines persistence and `app/schemas` validates API contracts.

Memberships carry tenant-specific roles. `Actor` wraps the persisted account per request and prevents organization selection from mutating global account data. Organization/resource checks precede mutations. Background reminders open their own database session; resource events are committed with their changes. Unique constraints and row locks protect refresh rotation, dependency graphs, assignment membership checks and repeated reminder deliveries.

Files remain private on disk and are streamed only after authorization. API failures use a single structured error envelope. Secret or validation input values are not included in validation errors.
