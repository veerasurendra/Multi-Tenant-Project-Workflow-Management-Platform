"""Validate migrations in an isolated PostgreSQL schema, never in public."""
import re
import uuid
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from app.database import engine

schema = "pm_migration_test_" + uuid.uuid4().hex
assert re.fullmatch(r"pm_migration_test_[a-f0-9]{32}", schema)
with engine.connect() as connection:
    connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    connection.commit()
    try:
        connection.execute(text(f'SET search_path TO "{schema}"'))
        connection.commit()
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        command.upgrade(config, "dbe5cba1f574")
        connection.execute(text("INSERT INTO users (full_name,email,password,role,is_active) VALUES ('Legacy User','legacy@example.com','test','admin',true)"))
        connection.execute(text("INSERT INTO projects (name,created_by,is_deleted) VALUES ('Legacy Project',1,false)"))
        connection.execute(text("INSERT INTO tasks (title,status,priority,project_id,created_by,is_deleted) VALUES ('Legacy task','pending','medium',1,1,false)"))
        connection.commit()
        command.upgrade(config, "head")
        assert connection.execute(text("SELECT role FROM users WHERE id=1")).scalar() == "organization_admin"
        assert connection.execute(text("SELECT status FROM tasks WHERE id=1")).scalar() == "todo"
        assert connection.execute(text("SELECT count(*) FROM organization_members")).scalar() == 1
        assert connection.execute(text("SELECT count(*) FROM project_members")).scalar() == 1
        assert connection.execute(text("SELECT organization_id FROM tasks WHERE id=1")).scalar() is not None
        required = {"organizations", "organization_members", "refresh_tokens", "task_dependencies", "project_comments", "project_attachments", "reminder_deliveries"}
        assert required <= set(inspect(connection).get_table_names(schema=schema))
        print("PostgreSQL migration passed: fresh schema and legacy data upgrade")
        connection.rollback()
    finally:
        connection.rollback()
        connection.execute(text('SET search_path TO public'))
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        connection.commit()
