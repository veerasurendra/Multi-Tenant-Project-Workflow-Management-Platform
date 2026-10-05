import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
import re
import uuid
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

POSTGRES_TEST = os.environ.get("PM_TEST_POSTGRES") == "1"
TEST_SCHEMA = "pm_api_test_" + uuid.uuid4().hex
if POSTGRES_TEST:
    from app.config import settings
    control_engine = create_engine(settings.DATABASE_URL)
    engine = create_engine(settings.DATABASE_URL, connect_args={"options": f"-csearch_path={TEST_SCHEMA}"})
else:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)

@pytest.fixture(scope="session", autouse=True)
def isolated_postgres_schema():
    if POSTGRES_TEST:
        assert re.fullmatch(r"pm_api_test_[a-f0-9]{32}", TEST_SCHEMA)
        with control_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{TEST_SCHEMA}"'))
    yield
    if POSTGRES_TEST:
        engine.dispose()
        with control_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{TEST_SCHEMA}" CASCADE'))
        control_engine.dispose()

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "REMINDERS_ENABLED", False)
    with TestClient(app) as test_client:
        yield test_client


def register_and_login(client, email, role="member", password="password123"):
    from app import models
    from app.security import hash_password
    role = {"admin": models.RoleEnum.admin, "manager": models.RoleEnum.project_manager, "member": models.RoleEnum.team_member, "viewer": models.RoleEnum.viewer}[role]
    with TestingSessionLocal() as db:
        org = db.query(models.Organization).filter_by(slug="test-organization").first()
        if not org:
            org = models.Organization(name="Test organization", slug="test-organization")
            db.add(org); db.flush()
        user = models.User(full_name=email.split("@")[0].title(), email=email, password=hash_password(password), role=role, organization_id=org.id)
        db.add(user); db.flush()
        db.add(models.OrganizationMember(user_id=user.id, organization_id=org.id, role=role.value))
        db.commit()
    resp = client.post("/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture()
def admin_headers(client):
    return register_and_login(client, "admin@example.com", role="admin")


@pytest.fixture()
def manager_headers(client):
    return register_and_login(client, "manager@example.com", role="manager")


@pytest.fixture()
def member_headers(client):
    return register_and_login(client, "member@example.com", role="member")
