def _setup_project_with_member(client, manager_headers, member_headers):
    create = client.post(
        "/projects", json={"name": "Activity Project", "description": "x"}, headers=manager_headers
    )
    project_id = create.json()["id"]
    me = client.get("/auth/me", headers=member_headers).json()
    client.post(
        f"/projects/{project_id}/members", json={"user_id": me["id"]}, headers=manager_headers
    )
    return project_id, me["id"]


def test_login_and_signup_are_logged(client, admin_headers):
    response = client.post("/api/auth/register", json={"full_name": "New Admin", "email": "new-admin@example.com", "password": "password123", "organization_name": "New organization"})
    assert response.status_code == 201
    login = client.post("/api/auth/login", data={"username": "new-admin@example.com", "password": "password123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = client.get("/activities", headers=headers)
    assert resp.status_code == 200
    actions = [a["action"] for a in resp.json()["items"]]
    assert "SIGNUP" in actions
    assert "LOGIN" in actions



def test_non_admin_cannot_view_full_feed(client, member_headers):
    resp = client.get("/activities", headers=member_headers)
    assert resp.status_code == 403


def test_logout_is_logged(client, member_headers):
    login = client.post("/auth/login", data={"username": "member@example.com", "password": "password123"}).json()
    resp = client.post("/auth/logout", json={"refresh_token": login["refresh_token"]}, headers=member_headers)
    assert resp.status_code == 200

    me = client.get("/auth/me", headers=member_headers).json()
    activities = client.get(f"/activities/user/{me['id']}", headers=member_headers).json()
    actions = [a["action"] for a in activities["items"]]
    assert "LOGOUT" in actions


def test_user_can_view_own_activity_but_not_others(client, manager_headers, member_headers):
    manager_me = client.get("/auth/me", headers=manager_headers).json()
    member_me = client.get("/auth/me", headers=member_headers).json()

    resp = client.get(f"/activities/user/{member_me['id']}", headers=member_headers)
    assert resp.status_code == 200

    resp = client.get(f"/activities/user/{manager_me['id']}", headers=member_headers)
    assert resp.status_code == 403


def test_admin_can_view_any_users_activity(client, admin_headers, member_headers):
    member_me = client.get("/auth/me", headers=member_headers).json()
    resp = client.get(f"/activities/user/{member_me['id']}", headers=admin_headers)
    assert resp.status_code == 200


def test_project_activity_includes_project_and_task_events(client, manager_headers, member_headers):
    project_id, member_id = _setup_project_with_member(client, manager_headers, member_headers)
    client.post(
        "/tasks",
        json={"title": "T1", "assigned_to": member_id, "project_id": project_id},
        headers=manager_headers,
    )

    resp = client.get(f"/activities/project/{project_id}", headers=manager_headers)
    assert resp.status_code == 200
    actions = [a["action"] for a in resp.json()["items"]]
    assert "PROJECT_CREATED" in actions
    assert "MEMBER_ADDED" in actions
    assert "TASK_CREATED" in actions


def test_project_activity_forbidden_for_non_members(client, manager_headers, member_headers, admin_headers):
    # A second, unrelated member should not see this project's activity.
    project_id, _ = _setup_project_with_member(client, manager_headers, member_headers)

    from tests.conftest import register_and_login
    outsider_headers = register_and_login(client, "outsider@example.com")

    resp = client.get(f"/activities/project/{project_id}", headers=outsider_headers)
    assert resp.status_code == 403


def test_filter_activities_by_action_and_entity_type(client, admin_headers, manager_headers):
    client.post("/projects", json={"name": "P1", "description": "x"}, headers=manager_headers)

    resp = client.get(
        "/activities", params={"action": "PROJECT_CREATED", "entity_type": "Project"}, headers=admin_headers
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    assert all(a["action"] == "PROJECT_CREATED" for a in items)


def test_filter_activities_by_date_range_excludes_out_of_range(client, admin_headers, manager_headers):
    client.post("/projects", json={"name": "P2", "description": "x"}, headers=manager_headers)

    # A date_from far in the future should exclude everything.
    resp = client.get(
        "/activities", params={"date_from": "2999-01-01T00:00:00Z"}, headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_export_activities_csv(client, admin_headers, manager_headers):
    client.post("/projects", json={"name": "P3", "description": "x"}, headers=manager_headers)

    resp = client.get("/activities/export/csv", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "PROJECT_CREATED" in resp.text
