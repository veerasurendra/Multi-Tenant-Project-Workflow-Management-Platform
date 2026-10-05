def _setup_project_with_member(client, manager_headers, member_headers):
    create = client.post(
        "/projects", json={"name": "Audit Project", "description": "original desc"}, headers=manager_headers
    )
    project_id = create.json()["id"]
    me = client.get("/auth/me", headers=member_headers).json()
    client.post(
        f"/projects/{project_id}/members", json={"user_id": me["id"]}, headers=manager_headers
    )
    return project_id, me["id"]


def test_task_status_change_recorded_in_audit_trail(client, manager_headers, member_headers):
    project_id, member_id = _setup_project_with_member(client, manager_headers, member_headers)
    task = client.post(
        "/tasks",
        json={"title": "Track me", "assigned_to": member_id, "project_id": project_id},
        headers=manager_headers,
    ).json()

    for workflow_status in ("in_progress", "review", "done"):
        response = client.put(f"/tasks/{task['id']}", json={"status": workflow_status}, headers=member_headers)
        assert response.status_code == 200

    resp = client.get(f"/audit-logs/Task/{task['id']}", headers=manager_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    status_changes = [a for a in items if a["field_name"] == "status"]
    assert len(status_changes) == 3
    assert status_changes[0]["old_value"] == "todo"
    # ordering is chronological (asc), so first change should be Pending -> In Progress
    assert status_changes[0]["new_value"] == "in_progress"
    assert status_changes[2]["new_value"] == "done"


def test_project_field_changes_recorded_in_audit_trail(client, manager_headers):
    create = client.post(
        "/projects", json={"name": "Original Name", "description": "Original"}, headers=manager_headers
    )
    project_id = create.json()["id"]

    client.put(
        f"/projects/{project_id}", json={"name": "New Name"}, headers=manager_headers
    )
    client.put(
        f"/projects/{project_id}", json={"description": "New description"}, headers=manager_headers
    )

    resp = client.get(f"/audit-logs/Project/{project_id}", headers=manager_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    fields_changed = {a["field_name"] for a in items}
    assert "name" in fields_changed
    assert "description" in fields_changed

    name_change = next(a for a in items if a["field_name"] == "name")
    assert name_change["old_value"] == "Original Name"
    assert name_change["new_value"] == "New Name"


def test_no_audit_entry_when_value_unchanged(client, manager_headers):
    create = client.post(
        "/projects", json={"name": "Same Name", "description": "Same desc"}, headers=manager_headers
    )
    project_id = create.json()["id"]

    # Re-submit identical name; should not create a spurious audit row.
    client.put(f"/projects/{project_id}", json={"name": "Same Name"}, headers=manager_headers)

    resp = client.get(f"/audit-logs/Project/{project_id}", headers=manager_headers)
    items = resp.json()["items"]
    assert all(a["field_name"] != "name" for a in items)


def test_reassignment_recorded_in_audit_trail(client, manager_headers, member_headers):
    project_id, member_id = _setup_project_with_member(client, manager_headers, member_headers)
    task = client.post(
        "/tasks",
        json={"title": "Reassign audit", "project_id": project_id},
        headers=manager_headers,
    ).json()

    client.put(f"/tasks/{task['id']}", json={"assigned_to": member_id}, headers=manager_headers)

    resp = client.get(f"/audit-logs/Task/{task['id']}", headers=manager_headers)
    items = resp.json()["items"]
    assigned_changes = [a for a in items if a["field_name"] == "assigned_to"]
    assert len(assigned_changes) == 1
    assert assigned_changes[0]["old_value"] is None
    assert assigned_changes[0]["new_value"] == str(member_id)


def test_non_admin_cannot_view_full_audit_feed(client, member_headers):
    resp = client.get("/audit-logs", headers=member_headers)
    assert resp.status_code == 403


def test_admin_can_view_full_audit_feed_with_filters(client, admin_headers, manager_headers):
    create = client.post(
        "/projects", json={"name": "Filter Me", "description": "x"}, headers=manager_headers
    )
    project_id = create.json()["id"]
    client.put(f"/projects/{project_id}", json={"name": "Filter Me Updated"}, headers=manager_headers)

    resp = client.get("/audit-logs", params={"entity_type": "Project"}, headers=admin_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(a["entity_type"] == "Project" for a in items)
    assert any(a["new_value"] == "Filter Me Updated" for a in items)


def test_outsider_cannot_view_task_audit_trail(client, manager_headers, member_headers):
    project_id, member_id = _setup_project_with_member(client, manager_headers, member_headers)
    task = client.post(
        "/tasks",
        json={"title": "Private task", "assigned_to": member_id, "project_id": project_id},
        headers=manager_headers,
    ).json()
    client.put(f"/tasks/{task['id']}", json={"status": "in_progress"}, headers=member_headers)

    from tests.conftest import register_and_login
    outsider_headers = register_and_login(client, "outsider2@example.com")

    resp = client.get(f"/audit-logs/Task/{task['id']}", headers=outsider_headers)
    assert resp.status_code == 403


def test_export_audit_logs_csv(client, admin_headers, manager_headers):
    create = client.post(
        "/projects", json={"name": "CSV Export", "description": "x"}, headers=manager_headers
    )
    project_id = create.json()["id"]
    client.put(f"/projects/{project_id}", json={"name": "CSV Export Updated"}, headers=manager_headers)

    resp = client.get("/audit-logs/export/csv", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "CSV Export Updated" in resp.text
