"""Introduce tenants and refresh tokens, preserving pre-tenant data.
Revision ID: 0caaecd1c653
Revises: dbe5cba1f574
"""
from alembic import op
import sqlalchemy as sa
revision = "0caaecd1c653"
down_revision = "dbe5cba1f574"
branch_labels = depends_on = None

def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "organizations" not in inspector.get_table_names():
        op.create_table("organizations", sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(150), nullable=False), sa.Column("slug", sa.String(150), nullable=False, unique=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
        op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)
    # A single tenant represents the former non-tenant installation.
    if bind.execute(sa.text("SELECT COUNT(*) FROM users")).scalar():
        bind.execute(sa.text("INSERT INTO organizations (name, slug, is_active) SELECT 'Legacy organization', 'legacy-organization', true WHERE NOT EXISTS (SELECT 1 FROM organizations WHERE slug='legacy-organization')"))
    for table in ["users", "projects", "tasks", "project_members", "activity_logs", "audit_logs", "notifications"]:
        if "organization_id" not in {c["name"] for c in sa.inspect(bind).get_columns(table)}:
            with op.batch_alter_table(table) as batch:
                batch.add_column(sa.Column("organization_id", sa.Integer(), nullable=True))
                batch.create_index(f"ix_{table}_organization_id", ["organization_id"])
                batch.create_foreign_key(f"fk_{table}_organization", "organizations", ["organization_id"], ["id"], ondelete="RESTRICT" if table == "users" else "CASCADE")
    bind.execute(sa.text("UPDATE users SET organization_id=(SELECT id FROM organizations WHERE slug='legacy-organization') WHERE organization_id IS NULL"))
    for table, source, foreign in [("projects", "users", "created_by"), ("tasks", "projects", "project_id"), ("project_members", "projects", "project_id"), ("activity_logs", "users", "user_id"), ("audit_logs", "users", "changed_by"), ("notifications", "users", "user_id")]:
        bind.execute(sa.text(f"UPDATE {table} SET organization_id=(SELECT organization_id FROM {source} WHERE {source}.id={table}.{foreign}) WHERE organization_id IS NULL"))
        with op.batch_alter_table(table) as batch:
            batch.alter_column("organization_id", existing_type=sa.Integer(), nullable=False)
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(40) USING role::text")
        op.execute("DROP TYPE IF EXISTS roleenum")
    op.execute("UPDATE users SET role=CASE role WHEN 'admin' THEN 'organization_admin' WHEN 'manager' THEN 'project_manager' WHEN 'member' THEN 'team_member' ELSE role END")
    if bind.dialect.name == "postgresql":
        op.execute("CREATE TYPE roleenum AS ENUM ('super_admin', 'organization_admin', 'project_manager', 'team_member', 'viewer')")
        op.execute("ALTER TABLE users ALTER COLUMN role TYPE roleenum USING role::roleenum")
    if "refresh_tokens" not in sa.inspect(bind).get_table_names():
        op.create_table("refresh_tokens", sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("token", sa.String(500), nullable=False, unique=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
        op.create_index("ix_refresh_tokens_token", "refresh_tokens", ["token"], unique=True)

def downgrade():
    raise RuntimeError("Tenant migration is irreversible without an explicit data export and restore")
