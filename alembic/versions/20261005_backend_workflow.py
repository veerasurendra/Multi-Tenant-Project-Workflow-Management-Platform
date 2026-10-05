"""Organization memberships and complete backend workflow.
Revision ID: 20261005_backend
Revises: 0caaecd1c653
"""
from alembic import op
import sqlalchemy as sa
revision = "20261005_backend"
down_revision = "0caaecd1c653"
branch_labels = depends_on = None

def upgrade():
    bind = op.get_bind()
    # Older installations used enum names rather than workflow values.
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE tasks ALTER COLUMN status TYPE VARCHAR(30) USING status::text")
        op.execute("DROP TYPE IF EXISTS statusenum")
    op.execute("UPDATE tasks SET status=CASE status WHEN 'pending' THEN 'todo' WHEN 'Pending' THEN 'todo' WHEN 'In Progress' THEN 'in_progress' WHEN 'completed' THEN 'done' WHEN 'Completed' THEN 'done' ELSE status END")
    if bind.dialect.name == "postgresql":
        op.execute("CREATE TYPE statusenum AS ENUM ('backlog', 'todo', 'in_progress', 'blocked', 'review', 'done', 'cancelled')")
        op.execute("ALTER TABLE tasks ALTER COLUMN status TYPE statusenum USING status::statusenum")
    project_enum = sa.Enum("planning", "active", "on_hold", "completed", "archived", name="projectstatus")
    project_enum.create(bind, checkfirst=True)
    for table, columns in {
        "projects": [sa.Column("status", project_enum, nullable=False, server_default="planning"), sa.Column("start_date", sa.DateTime(timezone=True)), sa.Column("due_date", sa.DateTime(timezone=True)), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())],
        "tasks": [sa.Column("estimated_hours", sa.Float()), sa.Column("actual_hours", sa.Float()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("completed_at", sa.DateTime(timezone=True))],
        "task_attachments": [sa.Column("mime_type", sa.String(100), nullable=False, server_default="application/octet-stream"), sa.Column("file_size", sa.Integer(), nullable=False, server_default="0")],
        "activity_logs": [sa.Column("ip_address", sa.String(45)), sa.Column("metadata", sa.JSON())],
        "audit_logs": [sa.Column("ip_address", sa.String(45)), sa.Column("metadata", sa.JSON())],
    }.items():
        for column in columns: op.add_column(table, column)
    for table in ("activity_logs", "audit_logs"):
        with op.batch_alter_table(table) as batch:
            batch.alter_column("organization_id", existing_type=sa.Integer(), nullable=True)
    # New model tables have no dependencies on schema changes in later revisions.
    from app.models import OrganizationMember, TaskDependency, ProjectComment, ProjectAttachment, ReminderDelivery, RefreshToken
    for model in (OrganizationMember, TaskDependency, ProjectComment, ProjectAttachment, ReminderDelivery, RefreshToken):
        model.__table__.create(bind, checkfirst=True)
    op.execute("INSERT INTO organization_members (organization_id, user_id, role, is_active) SELECT organization_id, id, role, is_active FROM users WHERE organization_id IS NOT NULL AND role != 'super_admin'")
    # Ensure existing owners satisfy the same assignment membership rule as new owners.
    op.execute("INSERT INTO project_members (organization_id, project_id, user_id) SELECT organization_id, id, created_by FROM projects WHERE NOT EXISTS (SELECT 1 FROM project_members WHERE project_members.project_id=projects.id AND project_members.user_id=projects.created_by)")
    # Preserve pre-existing valid task assignees' project access.
    op.execute("INSERT INTO project_members (organization_id, project_id, user_id) SELECT DISTINCT tasks.organization_id, tasks.project_id, tasks.assigned_to FROM tasks JOIN organization_members ON organization_members.user_id=tasks.assigned_to AND organization_members.organization_id=tasks.organization_id JOIN users ON users.id=tasks.assigned_to WHERE tasks.assigned_to IS NOT NULL AND organization_members.is_active=true AND users.is_active=true AND organization_members.role != 'viewer' AND NOT EXISTS (SELECT 1 FROM project_members WHERE project_members.project_id=tasks.project_id AND project_members.user_id=tasks.assigned_to)")
    op.execute("UPDATE tasks SET completed_at=created_at WHERE status='done'")
    op.create_index("ix_tasks_due_date", "tasks", ["due_date"])
    op.create_index("ix_tasks_tenant_status", "tasks", ["organization_id", "status"])

def downgrade():
    for table in ("reminder_deliveries", "project_attachments", "project_comments", "task_dependencies", "organization_members"):
        op.drop_table(table)
    op.drop_index("ix_tasks_due_date", table_name="tasks")
    op.drop_index("ix_tasks_tenant_status", table_name="tasks")
    for table, columns in {"projects": ["status", "start_date", "due_date", "updated_at"], "tasks": ["estimated_hours", "actual_hours", "updated_at", "completed_at"], "task_attachments": ["mime_type", "file_size"], "activity_logs": ["ip_address", "metadata"], "audit_logs": ["ip_address", "metadata"]}.items():
        for column in columns: op.drop_column(table, column)
    # Preserve workflow values; rolling back application code requires a data migration.
