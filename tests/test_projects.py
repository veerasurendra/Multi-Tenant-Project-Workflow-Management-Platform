def test_member_cannot_create_project(client, member_headers):
    resp = client.post(
        "/projects", json={"name": "Blocked", "description": "x"}, headers=member_headers
    )
    assert resp.status_code == 403


def test_manager_can_create_project(client, manager_headers):
    resp = client.post(
        "/projects", json={"name": "Manager Project", "description": "x"}, headers=manager_headers
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Manager Project"


def test_admin_can_create_project(client, admin_headers):
    resp = client.post(
        "/projects", json={"name": "Admin Project", "description": "x"}, headers=admin_headers
    )
    assert resp.status_code == 201


def test_member_cannot_see_unrelated_project(client, manager_headers, member_headers):
    create = client.post(
        "/projects", json={"name": "Private", "description": "x"}, headers=manager_headers
    )
    project_id = create.json()["id"]
    resp = client.get(f"/projects/{project_id}", headers=member_headers)
    assert resp.status_code == 403


def test_member_can_see_project_after_added(client, manager_headers, member_headers):
    create = client.post(
        "/projects", json={"name": "Shared", "description": "x"}, headers=manager_headers
    )
    project_id = create.json()["id"]

    me = client.get("/auth/me", headers=member_headers).json()
    add_resp = client.post(
        f"/projects/{project_id}/members", json={"user_id": me["id"]}, headers=manager_headers
    )
    assert add_resp.status_code == 201

    resp = client.get(f"/projects/{project_id}", headers=member_headers)
    assert resp.status_code == 200


def test_project_members_list_includes_user_name(client, manager_headers, member_headers):
    create = client.post(
        "/projects", json={"name": "Team", "description": "x"}, headers=manager_headers
    )
    project_id = create.json()["id"]

    me = client.get("/auth/me", headers=member_headers).json()
    add_resp = client.post(
        f"/projects/{project_id}/members",
        json={"user_id": me["id"]},
        headers=manager_headers,
    )
    assert add_resp.status_code == 201

    resp = client.get(f"/projects/{project_id}/members", headers=manager_headers)
    assert resp.status_code == 200
    members = resp.json()
    member = next(m for m in members if m["user_id"] == me["id"])
    assert member["user_name"] == me["full_name"]


def test_manager_cannot_update_project_owned_by_another_manager(client, manager_headers, admin_headers):
    other_manager_headers = _register_second_manager(client)
    create = client.post(
        "/projects", json={"name": "OwnedByOther", "description": "x"}, headers=other_manager_headers
    )
    project_id = create.json()["id"]

    resp = client.put(
        f"/projects/{project_id}", json={"name": "Hijacked"}, headers=manager_headers
    )
    assert resp.status_code == 403

    # Admin can still update any project
    resp = client.put(
        f"/projects/{project_id}", json={"name": "AdminEdited"}, headers=admin_headers
    )
    assert resp.status_code == 200


def test_admin_can_update_and_delete_any_project(client, manager_headers, admin_headers):
    create = client.post(
        "/projects",
        json={"name": "AdminManaged", "description": "x"},
        headers=manager_headers,
    )
    project_id = create.json()["id"]

    update = client.put(
        f"/projects/{project_id}",
        json={"name": "AdminUpdated", "description": "changed"},
        headers=admin_headers,
    )
    assert update.status_code == 200
    assert update.json()["name"] == "AdminUpdated"
    assert update.json()["description"] == "changed"

    delete = client.delete(f"/projects/{project_id}", headers=admin_headers)
    assert delete.status_code == 204

    get_deleted = client.get(f"/projects/{project_id}", headers=admin_headers)
    assert get_deleted.status_code == 404


def _register_second_manager(client):
    from tests.conftest import register_and_login
    return register_and_login(client, "manager2@example.com", role="manager")



def test_only_admin_can_delete_project(client, manager_headers, admin_headers):
    create = client.post(
        "/projects", json={"name": "ToDelete", "description": "x"}, headers=manager_headers
    )
    project_id = create.json()["id"]

    # Manager who owns it still cannot delete (deletion is Admin-only per role matrix)
    resp = client.delete(f"/projects/{project_id}", headers=manager_headers)
    assert resp.status_code == 403

    resp = client.delete(f"/projects/{project_id}", headers=admin_headers)
    assert resp.status_code == 204


def test_project_list_is_paginated(client, admin_headers):
    for i in range(3):
        client.post(
            "/projects", json={"name": f"Proj {i}", "description": "x"}, headers=admin_headers
        )
    resp = client.get("/projects?page=1&page_size=2", headers=admin_headers)
    body = resp.json()
    assert resp.status_code == 200
    assert body["page_size"] == 2
    assert len(body["items"]) == 2
    assert body["total"] >= 3
