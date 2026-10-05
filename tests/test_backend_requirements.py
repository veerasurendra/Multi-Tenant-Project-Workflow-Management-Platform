from datetime import datetime, timedelta, timezone
import io
import pytest
from app import models
from app.security import create_access_token, create_refresh_token
from tests.conftest import TestingSessionLocal


def register(client, suffix):
    response = client.post("/api/auth/register", json={"full_name": suffix, "email": f"{suffix}@example.com", "password": "password123", "organization_name": suffix})
    assert response.status_code == 201, response.text
    login = client.post("/api/auth/login", data={"username": f"{suffix}@example.com", "password": "password123"})
    assert login.status_code == 200, login.text
    return response.json(), {"Authorization": f"Bearer {login.json()['access_token']}"}, login.json()


def project(client, headers, name="Project"):
    response = client.post("/api/projects", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def task(client, headers, project_id, **kwargs):
    response = client.post("/api/tasks", json={"project_id": project_id, "title": "Task", **kwargs}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def team(client, manager_headers, member_headers):
    p = project(client, manager_headers)
    member = client.get("/api/auth/me", headers=member_headers).json()
    response = client.post(f"/api/projects/{p['id']}/members", headers=manager_headers, json={"user_id": member["id"]})
    assert response.status_code == 201, response.text
    return p, member


def test_refresh_rotation_logout_and_change_password(client):
    user, headers, tokens = register(client, "tokens")
    refresh = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh.status_code == 200
    assert refresh.json()["refresh_token"] != tokens["refresh_token"]
    assert client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401
    rotated = refresh.json()
    assert client.post("/api/auth/logout", json={"refresh_token": rotated["refresh_token"]}, headers=headers).status_code == 200
    assert client.post("/api/auth/refresh", json={"refresh_token": rotated["refresh_token"]}).status_code == 401
    assert client.post("/api/auth/change-password", headers=headers, json={"current_password": "wrong", "new_password": "newpassword123"}).status_code == 400
    assert client.post("/api/auth/change-password", headers=headers, json={"current_password": "password123", "new_password": "newpassword123"}).status_code == 200
    assert client.post("/api/auth/login", data={"username": "tokens@example.com", "password": "password123"}).status_code == 401
    assert client.post("/api/auth/login", data={"username": "tokens@example.com", "password": "newpassword123"}).status_code == 200


def test_expired_access_refresh_and_inactive_user(client):
    user, headers, tokens = register(client, "expired")
    expired = create_access_token({"sub": str(user["id"])}, timedelta(seconds=-1))
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    raw = create_refresh_token({"sub": str(user["id"])}, timedelta(seconds=-1))
    assert client.post("/api/auth/refresh", json={"refresh_token": raw}).status_code == 401
    with TestingSessionLocal() as db:
        db.get(models.User, user["id"]).is_active = False; db.commit()
    assert client.get("/api/auth/me", headers=headers).status_code == 403
    assert client.post("/api/auth/login", data={"username": "expired@example.com", "password": "password123"}).status_code == 403
    assert client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 403


def test_multi_tenant_isolation_and_multi_membership(client):
    first, ah, _ = register(client, "tenant-a")
    second, bh, _ = register(client, "tenant-b")
    p = project(client, ah); t = task(client, ah, p["id"])
    for path in [f"/api/projects/{p['id']}", f"/api/tasks/{t['id']}", f"/api/tasks/{t['id']}/comments", f"/api/projects/{p['id']}/attachments", f"/api/activities/project/{p['id']}", f"/api/audit-logs/Task/{t['id']}"]:
        assert client.get(path, headers=bh).status_code in (403, 404)
    assert client.put(f"/api/tasks/{t['id']}", json={"title": "hacked"}, headers=bh).status_code == 404
    assert client.delete(f"/api/projects/{p['id']}", headers=bh).status_code == 404
    assert client.get("/api/tasks", headers=bh).json()["total"] == 0
    assert client.get("/api/auth/me", headers={**bh, "X-Organization-ID": str(first["organization_id"])}).status_code == 403
    add = client.post(f"/api/organizations/{first['organization_id']}/members", json={"user_id": second["id"], "role": "viewer"}, headers=ah)
    assert add.status_code == 201
    scoped = {**bh, "X-Organization-ID": str(first["organization_id"])}
    assert client.get("/api/auth/me", headers=scoped).json()["role"] == "viewer"
    assert client.get("/api/auth/me", headers=bh).json()["role"] == "organization_admin"
    assert client.get(f"/api/projects/{p['id']}", headers=scoped).status_code == 403
    assert client.post(f"/api/projects/{p['id']}/members", json={"user_id": second["id"]}, headers=ah).status_code == 201
    assert client.get(f"/api/projects/{p['id']}", headers=scoped).status_code == 200
    assert client.post(f"/api/tasks/{t['id']}/comments", json={"comment": "no"}, headers=scoped).status_code == 403
    assert client.patch(f"/api/tasks/{t['id']}/assign", json={"assigned_to": second["id"]}, headers=ah).status_code == 400


def test_organization_crud_membership_and_last_admin(client, admin_headers, member_headers):
    admin = client.get("/api/auth/me", headers=admin_headers).json()
    org_id = admin["organization_id"]
    assert client.get(f"/api/organizations/{org_id}", headers=admin_headers).status_code == 200
    assert client.patch(f"/api/organizations/{org_id}", headers=admin_headers, json={"name": "Updated"}).json()["name"] == "Updated"
    assert client.patch(f"/api/organizations/{org_id}", headers=member_headers, json={"name": "hacked"}).status_code == 403
    assert client.delete(f"/api/organizations/{org_id}/members/{admin['id']}", headers=admin_headers).status_code == 409
    body = {"full_name": "Invited", "email": "invited@example.com", "password": "password123", "role": "team_member"}
    response = client.post(f"/api/organizations/{org_id}/members", headers=admin_headers, json=body)
    assert response.status_code == 201
    uid = response.json()["user_id"]
    assert client.post(f"/api/organizations/{org_id}/members", headers=admin_headers, json={"user_id": uid}).status_code == 409
    assert client.patch(f"/api/organizations/{org_id}/members/{uid}", headers=admin_headers, json={"role": "super_admin"}).status_code == 403
    assert client.patch(f"/api/organizations/{org_id}/members/{uid}", headers=admin_headers, json={"role": "bogus"}).status_code == 422
    assert client.patch(f"/api/organizations/{org_id}/members/{uid}", headers=admin_headers, json={"is_active": False}).status_code == 200
    assert client.post("/api/auth/login", data={"username": body["email"], "password": body["password"]}).status_code == 403
    assert client.patch(f"/api/organizations/{org_id}/members/{uid}", headers=admin_headers, json={"is_active": True}).status_code == 200
    assert client.delete(f"/api/organizations/{org_id}/members/{uid}", headers=admin_headers).status_code == 204
    new = client.post("/api/organizations", headers=admin_headers, json={"name": "Another org"})
    assert new.status_code == 201
    assert len(client.get("/api/organizations", headers=admin_headers).json()) == 2


def test_assignment_rules_and_project_removal(client, manager_headers, member_headers):
    p = project(client, manager_headers)
    member = client.get("/api/auth/me", headers=member_headers).json()
    t = task(client, manager_headers, p["id"])
    path = f"/api/tasks/{t['id']}/assign"
    assert client.patch(path, headers=manager_headers, json={"assigned_to": member["id"]}).status_code == 400
    outsider, _, _ = register(client, "foreign")
    assert client.patch(path, headers=manager_headers, json={"assigned_to": outsider["id"]}).status_code == 400
    assert client.post(f"/api/projects/{p['id']}/members", headers=manager_headers, json={"user_id": outsider["id"]}).status_code == 400
    assert client.post(f"/api/projects/{p['id']}/members", headers=manager_headers, json={"user_id": member["id"]}).status_code == 201
    assert client.post(f"/api/projects/{p['id']}/members", headers=manager_headers, json={"user_id": member["id"]}).status_code == 409
    with TestingSessionLocal() as db:
        db.get(models.User, member["id"]).is_active = False; db.commit()
    assert client.patch(path, headers=manager_headers, json={"assigned_to": member["id"]}).status_code == 400
    with TestingSessionLocal() as db:
        db.get(models.User, member["id"]).is_active = True; db.commit()
    assert client.patch(path, headers=manager_headers, json={"assigned_to": member["id"]}).status_code == 200
    assert client.delete(f"/api/projects/{p['id']}/members/{member['id']}", headers=manager_headers).status_code == 409
    assert client.patch(path, headers=manager_headers, json={"assigned_to": None}).status_code == 200
    assert client.delete(f"/api/projects/{p['id']}/members/{member['id']}", headers=manager_headers).status_code == 204


def test_workflow_dependencies_and_cycles(client, manager_headers):
    p = project(client, manager_headers)
    a, b, c = [task(client, manager_headers, p["id"], title=name) for name in ("A", "B", "C")]
    def link(target, source):
        return client.post(f"/api/tasks/{target['id']}/dependencies", headers=manager_headers, json={"depends_on_id": source["id"]})
    assert link(b, a).status_code == 201
    assert link(c, b).status_code == 201
    assert link(a, c).status_code == 409
    assert link(a, a).status_code == 409
    assert link(b, a).status_code == 409
    assert client.patch(f"/api/tasks/{b['id']}/status", headers=manager_headers, json={"status": "in_progress"}).status_code == 409
    assert client.patch(f"/api/tasks/{a['id']}/status", headers=manager_headers, json={"status": "done"}).status_code == 409
    for status in ("in_progress", "review", "done"):
        assert client.patch(f"/api/tasks/{a['id']}/status", headers=manager_headers, json={"status": status}).status_code == 200
    assert client.patch(f"/api/tasks/{b['id']}/status", headers=manager_headers, json={"status": "in_progress"}).status_code == 200
    assert client.delete(f"/api/tasks/{a['id']}", headers=manager_headers).status_code == 409
    assert len(client.get(f"/api/tasks/{b['id']}/dependencies", headers=manager_headers).json()) == 1
    assert client.delete(f"/api/tasks/{b['id']}/dependencies/{a['id']}", headers=manager_headers).status_code == 204


def test_project_workflow_dates_and_task_moves(client, manager_headers, member_headers):
    p, member = team(client, manager_headers, member_headers)
    assert client.patch(f"/api/projects/{p['id']}", headers=manager_headers, json={"status": "completed"}).status_code == 409
    for status in ("active", "on_hold", "active", "completed"):
        assert client.patch(f"/api/projects/{p['id']}", headers=manager_headers, json={"status": status}).status_code == 200
    assert client.patch(f"/api/projects/{p['id']}", headers=manager_headers, json={"start_date": "2026-10-10T00:00:00Z", "due_date": "2026-10-01T00:00:00Z"}).status_code == 422
    t = task(client, manager_headers, p["id"], assigned_to=member["id"], estimated_hours=4, actual_hours=1)
    other = project(client, manager_headers, "Destination")
    assert client.post(f"/api/tasks/{t['id']}/move", headers=manager_headers, json={"project_id": other["id"]}).status_code == 400
    assert client.patch(f"/api/tasks/{t['id']}/assign", headers=manager_headers, json={"assigned_to": None}).status_code == 200
    assert client.post(f"/api/tasks/{t['id']}/move", headers=manager_headers, json={"project_id": other["id"]}).json()["project_id"] == other["id"]
    assert client.post(f"/api/projects/{other['id']}/archive", headers=manager_headers).status_code == 200
    assert client.patch(f"/api/tasks/{t['id']}", headers=manager_headers, json={"title": "blocked"}).status_code == 409


@pytest.mark.parametrize("kind", ["tasks", "projects"])
def test_comments_files_mentions_and_authorization(client, manager_headers, member_headers, kind):
    p, member = team(client, manager_headers, member_headers)
    row = task(client, manager_headers, p["id"], assigned_to=member["id"]) if kind == "tasks" else p
    base = f"/api/{kind}/{row['id']}"
    response = client.post(base+"/comments", headers=manager_headers, json={"comment": "Please check @member"})
    assert response.status_code == 201
    cid = response.json()["id"]
    assert client.patch(base+f"/comments/{cid}", headers=member_headers, json={"comment": "hacked"}).status_code == 403
    assert client.delete(base+f"/comments/{cid}", headers=member_headers).status_code == 403
    assert client.patch(base+f"/comments/{cid}", headers=manager_headers, json={"comment": "Updated"}).status_code == 200
    assert client.delete(base+f"/comments/{cid}", headers=manager_headers).status_code == 204
    assert any(n["notification_type"] == "user_mentioned" for n in client.get("/api/notifications", headers=member_headers).json())
    valid = client.post(base+"/attachments", headers=member_headers, files={"file": ("../notes.txt", b"hello", "text/plain")})
    assert valid.status_code == 201, valid.text
    assert valid.json()["file_size"] == 5
    download = client.get(base+f"/attachments/{valid.json()['id']}/download", headers=manager_headers)
    assert download.content == b"hello"
    assert client.post(base+"/attachments", headers=member_headers, files={"file": ("fake.png", b"not an image", "image/png")}).status_code == 400
    assert client.post(base+"/attachments", headers=member_headers, files={"file": ("bad.exe", b"MZ", "application/octet-stream")}).status_code == 400
    assert client.post(base+"/attachments", headers=member_headers, files={"file": ("notes.txt", b"hello", "image/png")}).status_code == 400


def test_size_empty_and_real_image_validation(client, manager_headers, monkeypatch):
    from PIL import Image
    from app.config import settings
    p = project(client, manager_headers)
    path = f"/api/projects/{p['id']}/attachments"
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 4)
    assert client.post(path, headers=manager_headers, files={"file": ("large.txt", b"12345", "text/plain")}).status_code == 413
    assert client.post(path, headers=manager_headers, files={"file": ("empty.txt", b"", "text/plain")}).status_code == 400
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 1024*1024)
    image = io.BytesIO(); Image.new("RGB", (8,8)).save(image, format="PNG")
    assert client.post(path, headers=manager_headers, files={"file": ("real.png", image.getvalue(), "image/png")}).status_code == 201


def test_dashboards_search_filters_and_reminders(client, admin_headers, manager_headers, member_headers):
    p, member = team(client, manager_headers, member_headers)
    now = datetime.now(timezone.utc)
    task(client, manager_headers, p["id"], title="Payment late", priority="high", assigned_to=member["id"], due_date=(now-timedelta(days=1)).isoformat())
    task(client, manager_headers, p["id"], title="Payment soon", priority="low", assigned_to=member["id"], due_date=(now+timedelta(hours=2)).isoformat())
    task(client, manager_headers, p["id"], title="Other", priority="low")
    response = client.get("/api/tasks", headers=manager_headers, params={"search": "payment", "assignee_id": member["id"], "sort_by": "title", "sort_order": "asc", "page_size": 1, "page": 2})
    assert response.status_code == 200
    assert response.json()["total"] == 2 and response.json()["items"][0]["title"] == "Payment soon"
    assert client.get("/api/tasks", headers=manager_headers, params={"priority": "high", "due_to": now.isoformat()}).json()["total"] == 1
    sorted_tasks = client.get("/api/tasks", headers=manager_headers, params={"sort_by": "priority", "sort_order": "asc"}).json()["items"]
    assert [t["priority"] for t in sorted_tasks] == ["low", "low", "high"]
    assert client.get("/api/tasks", headers=manager_headers, params={"created_from": (now+timedelta(days=1)).isoformat()}).json()["total"] == 0
    assert client.get("/api/dashboard", headers=admin_headers).json()["total_tasks"] == 3
    assert client.get("/api/dashboard", headers=manager_headers).json()["my_projects"] == 1
    assert client.get("/api/dashboard", headers=member_headers).json()["my_tasks"] == 2
    assert client.get("/api/dashboard", headers=member_headers).json()["overdue_tasks"] == 1
    assert client.post("/api/notifications/process-reminders", headers=member_headers).status_code == 403
    assert client.post("/api/notifications/process-reminders", headers=admin_headers).json()["processed"] == 2
    assert client.post("/api/notifications/process-reminders", headers=admin_headers).json()["processed"] == 0
    notifications = client.get("/api/notifications", headers=member_headers).json()
    assert {"task_overdue", "task_due_soon"} <= {n["notification_type"] for n in notifications}
    assert client.patch(f"/api/notifications/{notifications[0]['id']}/read", headers=member_headers).status_code == 200
    assert client.patch("/api/notifications/read-all", headers=member_headers).status_code == 200
    assert client.get("/api/notifications/unread/count", headers=member_headers).json()["unread_count"] == 0


def test_error_format_and_audit_metadata(client, manager_headers):
    p = project(client, manager_headers)
    response = client.get("/api/tasks/999999", headers=manager_headers)
    assert response.json() == {"success": False, "error": {"code": "NOT_FOUND", "message": "Task not found"}}
    assert client.post("/api/tasks", headers=manager_headers, json={}).json()["error"]["code"] == "VALIDATION_ERROR"
    client.patch(f"/api/projects/{p['id']}", headers=manager_headers, json={"name": "Changed"})
    audit = client.get(f"/api/audit-logs/Project/{p['id']}", headers=manager_headers).json()["items"]
    assert audit[0]["ip_address"] == "testclient"
    assert isinstance(audit[0]["event_metadata"], dict)
    assert client.patch(f"/api/audit-logs/Project/{p['id']}", headers=manager_headers, json={}).status_code == 405


def test_super_admin_global_and_selected_tenant_access(client):
    from app.security import hash_password
    first, ah, _ = register(client, "global-a")
    second, bh, _ = register(client, "global-b")
    pa = project(client, ah); pb = project(client, bh)
    ta = task(client, ah, pa["id"])
    with TestingSessionLocal() as db:
        account = models.User(full_name="Super", email="super@example.com", password=hash_password("password123"), role=models.RoleEnum.super_admin)
        db.add(account); db.commit()
    login = client.post("/api/auth/login", data={"username": "super@example.com", "password": "password123"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/projects", headers=headers).json()["total"] == 2
    assert client.get(f"/api/tasks/{ta['id']}", headers=headers).status_code == 200
    assert client.patch(f"/api/tasks/{ta['id']}", headers=headers, json={"title": "Global edit"}).status_code == 200
    logs = client.get("/api/audit-logs", headers=headers).json()["items"]
    assert logs[0]["organization_id"] == first["organization_id"]
    assert client.post("/api/projects", headers=headers, json={"name": "Unscoped"}).status_code == 403
    selected = {**headers, "X-Organization-ID": str(second["organization_id"])}
    assert client.post("/api/projects", headers=selected, json={"name": "Selected"}).status_code == 201
    assert client.get("/api/dashboard", headers=selected).json()["total_projects"] == 2
    assert client.get("/api/activities", headers=headers).status_code == 200


def test_notification_tenant_scope_and_fallback_membership(client):
    first, ah, _ = register(client, "scope-a")
    second, bh, _ = register(client, "scope-b")
    member, mh, _ = register(client, "scope-member")
    for org, headers in ((first, ah), (second, bh)):
        assert client.post(f"/api/organizations/{org['organization_id']}/members", headers=headers, json={"user_id": member["id"], "role": "team_member"}).status_code == 201
        p = project(client, headers)
        assert client.post(f"/api/projects/{p['id']}/members", headers=headers, json={"user_id": member["id"]}).status_code == 201
    selected_a = {**mh, "X-Organization-ID": str(first["organization_id"])}
    selected_b = {**mh, "X-Organization-ID": str(second["organization_id"])}
    notifications_a = client.get("/api/notifications", headers=selected_a).json()
    assert len(notifications_a) == 1
    assert client.patch(f"/api/notifications/{notifications_a[0]['id']}/read", headers=selected_b).status_code == 404
    assert len(client.get("/api/notifications", headers=selected_b).json()) == 1
    # A disabled primary membership does not disable other active memberships.
    with TestingSessionLocal() as db:
        membership = db.query(models.OrganizationMember).filter_by(user_id=member["id"], organization_id=member["organization_id"]).first()
        membership.is_active = False; db.commit()
    assert client.post("/api/auth/login", data={"username": "scope-member@example.com", "password": "password123"}).status_code == 200
    assert client.get("/api/auth/me", headers=mh).json()["organization_id"] in {first["organization_id"], second["organization_id"]}
    assert client.get("/api/auth/me", headers={**mh, "X-Organization-ID": str(member["organization_id"])}).status_code == 403


def test_task_priority_hours_due_today_and_recent_completion(client, manager_headers, member_headers):
    p, member = team(client, manager_headers, member_headers)
    now = datetime.now(timezone.utc)
    t = task(client, manager_headers, p["id"], assigned_to=member["id"], due_date=now.isoformat())
    assert client.get("/api/dashboard", headers=member_headers).json()["tasks_due_today"] == 1
    assert client.patch(f"/api/tasks/{t['id']}/priority", headers=member_headers, json={"priority": "high"}).status_code == 403
    assert client.patch(f"/api/tasks/{t['id']}/priority", headers=manager_headers, json={"priority": "high"}).json()["priority"] == "high"
    assert client.patch(f"/api/tasks/{t['id']}", headers=member_headers, json={"actual_hours": 3}).json()["actual_hours"] == 3
    assert client.patch(f"/api/tasks/{t['id']}", headers=member_headers, json={"actual_hours": -1}).status_code == 422
    for status in ("in_progress", "review", "done"):
        assert client.patch(f"/api/tasks/{t['id']}/status", headers=member_headers, json={"status": status}).status_code == 200
    dashboard = client.get("/api/dashboard", headers=member_headers).json()
    assert dashboard["recently_completed_tasks"] == 1 and dashboard["overdue_tasks"] == 0
    assert client.get("/api/dashboard", headers=manager_headers).json()["completed_tasks"] == 1


def test_deleted_project_hides_its_tasks_and_content(client, admin_headers):
    p = project(client, admin_headers); t = task(client, admin_headers, p["id"])
    assert client.delete(f"/api/projects/{p['id']}", headers=admin_headers).status_code == 204
    for suffix in ("", "/comments", "/attachments", "/dependencies"):
        assert client.get(f"/api/tasks/{t['id']}"+suffix, headers=admin_headers).status_code == 404
    assert client.patch(f"/api/tasks/{t['id']}", headers=admin_headers, json={"title": "Hidden"}).status_code == 404
