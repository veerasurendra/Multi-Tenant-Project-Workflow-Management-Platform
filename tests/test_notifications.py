def _setup_project_with_member(client, manager_headers, member_headers):
    create = client.post(
        "/projects", json={"name": "Notif Project", "description": "x"}, headers=manager_headers
    )
    project_id = create.json()["id"]
    me = client.get("/auth/me", headers=member_headers).json()
    client.post(
        f"/projects/{project_id}/members", json={"user_id": me["id"]}, headers=manager_headers
    )
    return project_id, me["id"]


def test_task_assignment_creates_notification(client, manager_headers, member_headers):
    project_id, member_id = _setup_project_with_member(client, manager_headers, member_headers)

    client.post(
        "/tasks",
        json={"title": "Do X", "assigned_to": member_id, "project_id": project_id},
        headers=manager_headers,
    )

    resp = client.get("/notifications", headers=member_headers)
    assert resp.status_code == 200
    notifications = resp.json()
    assert any(n["title"] == "Task Assigned" for n in notifications)
    assert any(n["notification_type"] == "TASK_ASSIGNED" for n in notifications)


def test_added_to_project_creates_notification(client, manager_headers, member_headers):
    _setup_project_with_member(client, manager_headers, member_headers)

    resp = client.get("/notifications", headers=member_headers)
    notifications = resp.json()
    assert any(n["title"] == "Added to Project" for n in notifications)


def test_unread_and_mark_read(client, manager_headers, member_headers):
    project_id, member_id = _setup_project_with_member(client, manager_headers, member_headers)
    client.post(
        "/tasks",
        json={"title": "Do X", "assigned_to": member_id, "project_id": project_id},
        headers=manager_headers,
    )

    unread = client.get("/notifications/unread", headers=member_headers).json()
    assert len(unread) >= 1

    count = client.get("/notifications/unread/count", headers=member_headers).json()
    assert count["unread_count"] == len(unread)

    notif_id = unread[0]["id"]
    resp = client.put(f"/notifications/{notif_id}/read", headers=member_headers)
    assert resp.status_code == 200
    assert resp.json()["is_read"] is True

    unread_after = client.get("/notifications/unread", headers=member_headers).json()
    assert len(unread_after) == len(unread) - 1


def test_mark_all_read(client, manager_headers, member_headers):
    project_id, member_id = _setup_project_with_member(client, manager_headers, member_headers)
    for i in range(3):
        client.post(
            "/tasks",
            json={"title": f"Task {i}", "assigned_to": member_id, "project_id": project_id},
            headers=manager_headers,
        )

    resp = client.put("/notifications/read-all", headers=member_headers)
    assert resp.status_code == 200
    assert resp.json()["updated_count"] >= 3

    unread = client.get("/notifications/unread", headers=member_headers).json()
    assert unread == []


def test_delete_notification_is_soft_and_hides_from_list(client, manager_headers, member_headers):
    project_id, member_id = _setup_project_with_member(client, manager_headers, member_headers)
    client.post(
        "/tasks",
        json={"title": "Do X", "assigned_to": member_id, "project_id": project_id},
        headers=manager_headers,
    )

    notifications = client.get("/notifications", headers=member_headers).json()
    notif_id = notifications[0]["id"]

    resp = client.delete(f"/notifications/{notif_id}", headers=member_headers)
    assert resp.status_code == 204

    remaining = client.get("/notifications", headers=member_headers).json()
    assert all(n["id"] != notif_id for n in remaining)

    # Deleting again (or reading) should 404 since it's gone from the user's view.
    resp = client.put(f"/notifications/{notif_id}/read", headers=member_headers)
    assert resp.status_code == 404


def test_cannot_access_another_users_notification(client, manager_headers, member_headers):
    project_id, member_id = _setup_project_with_member(client, manager_headers, member_headers)
    client.post(
        "/tasks",
        json={"title": "Do X", "assigned_to": member_id, "project_id": project_id},
        headers=manager_headers,
    )
    notif_id = client.get("/notifications", headers=member_headers).json()[0]["id"]

    # Manager (not the notification owner) tries to mark it read.
    resp = client.put(f"/notifications/{notif_id}/read", headers=manager_headers)
    assert resp.status_code == 404


def test_notification_preferences_default_enabled_and_can_be_disabled(client, member_headers):
    prefs = client.get("/notifications/preferences", headers=member_headers).json()
    assert len(prefs) > 0
    assert all(p["enabled"] is True for p in prefs)

    resp = client.put(
        "/notifications/preferences",
        json={"notification_type": "TASK_ASSIGNED", "enabled": False},
        headers=member_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"notification_type": "TASK_ASSIGNED", "enabled": False}

    prefs_after = client.get("/notifications/preferences", headers=member_headers).json()
    task_assigned_pref = next(p for p in prefs_after if p["notification_type"] == "TASK_ASSIGNED")
    assert task_assigned_pref["enabled"] is False


def test_disabled_preference_suppresses_notification(client, manager_headers, member_headers):
    project_id, member_id = _setup_project_with_member(client, manager_headers, member_headers)

    client.put(
        "/notifications/preferences",
        json={"notification_type": "TASK_ASSIGNED", "enabled": False},
        headers=member_headers,
    )

    client.post(
        "/tasks",
        json={"title": "Do X", "assigned_to": member_id, "project_id": project_id},
        headers=manager_headers,
    )

    notifications = client.get("/notifications", headers=member_headers).json()
    assert all(n["title"] != "Task Assigned" for n in notifications)


def test_task_reassignment_and_completion_notifications(client, manager_headers, member_headers):
    project_id, member_id = _setup_project_with_member(client, manager_headers, member_headers)
    manager_me = client.get("/auth/me", headers=manager_headers).json()

    task = client.post(
        "/tasks",
        json={"title": "Reassign me", "project_id": project_id},
        headers=manager_headers,
    ).json()

    # Reassign to member -> should notify them.
    client.put(
        f"/tasks/{task['id']}", json={"assigned_to": member_id}, headers=manager_headers
    )
    notifications = client.get("/notifications", headers=member_headers).json()
    assert any(n["title"] == "Task Reassigned" for n in notifications)

    # Member marks task completed -> creator (manager) should be notified.
    for workflow_status in ("in_progress", "review", "done"):
        response = client.put(f"/tasks/{task['id']}", json={"status": workflow_status}, headers=member_headers)
        assert response.status_code == 200
    manager_notifications = client.get("/notifications", headers=manager_headers).json()
    assert any(n["title"] == "Task Completed" for n in manager_notifications)


def test_task_deadline_update_notification(client, manager_headers, member_headers):
    project_id, member_id = _setup_project_with_member(client, manager_headers, member_headers)

    task = client.post(
        "/tasks",
        json={"title": "Deadline task", "assigned_to": member_id, "project_id": project_id},
        headers=manager_headers,
    ).json()

    client.put(
        f"/tasks/{task['id']}",
        json={"due_date": "2030-01-01T00:00:00Z"},
        headers=manager_headers,
    )

    notifications = client.get("/notifications", headers=member_headers).json()
    assert any(n["title"] == "Task Deadline Updated" for n in notifications)
