def _setup_project_with_member(client, manager_headers, member_headers):
    create = client.post(
        "/projects", json={"name": "Task Project", "description": "x"}, headers=manager_headers
    )
    project_id = create.json()["id"]
    me = client.get("/auth/me", headers=member_headers).json()
    client.post(
        f"/projects/{project_id}/members", json={"user_id": me["id"]}, headers=manager_headers
    )
    return project_id, me["id"]


def test_manager_can_create_and_assign_task(client, manager_headers, member_headers):
    project_id, member_id = _setup_project_with_member(client, manager_headers, member_headers)

    resp = client.post(
        "/tasks",
        json={
            "title": "Do the thing",
            "description": "details",
            "priority": "High",
            "assigned_to": member_id,
            "project_id": project_id,
        },
        headers=manager_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["assigned_to"] == member_id
    assert body["status"] == "Pending"


def test_member_cannot_create_task(client, manager_headers, member_headers):
    project_id, _ = _setup_project_with_member(client, manager_headers, member_headers)
    resp = client.post(
        "/tasks",
        json={"title": "Nope", "project_id": project_id},
        headers=member_headers,
    )
    assert resp.status_code == 403


def test_member_can_only_update_status_of_own_task(client, manager_headers, member_headers):
    project_id, member_id = _setup_project_with_member(client, manager_headers, member_headers)
    task = client.post(
        "/tasks",
        json={"title": "T1", "assigned_to": member_id, "project_id": project_id},
        headers=manager_headers,
    ).json()

    # Member updates status: allowed
    resp = client.put(
        f"/tasks/{task['id']}", json={"status": "In Progress"}, headers=member_headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "In Progress"

    # Member tries to change title: forbidden
    resp = client.put(
        f"/tasks/{task['id']}", json={"title": "Hacked"}, headers=member_headers
    )
    assert resp.status_code == 403


def test_member_cannot_update_task_not_assigned_to_them(client, manager_headers, member_headers):
    project_id, _ = _setup_project_with_member(client, manager_headers, member_headers)
    task = client.post(
        "/tasks",
        json={"title": "Unassigned task", "project_id": project_id},
        headers=manager_headers,
    ).json()

    resp = client.put(
        f"/tasks/{task['id']}", json={"status": "Completed"}, headers=member_headers
    )
    assert resp.status_code == 403


def test_manager_can_reassign_task(client, manager_headers, member_headers):
    project_id, member_id = _setup_project_with_member(client, manager_headers, member_headers)
    task = client.post(
        "/tasks",
        json={"title": "T2", "project_id": project_id},
        headers=manager_headers,
    ).json()

    resp = client.put(
        f"/tasks/{task['id']}", json={"assigned_to": member_id}, headers=manager_headers
    )
    assert resp.status_code == 200
    assert resp.json()["assigned_to"] == member_id


def test_manager_cannot_reassign_task_to_missing_user(client, manager_headers, member_headers):
    project_id, _ = _setup_project_with_member(client, manager_headers, member_headers)
    task = client.post(
        "/tasks",
        json={"title": "T3", "project_id": project_id},
        headers=manager_headers,
    ).json()

    resp = client.put(
        f"/tasks/{task['id']}", json={"assigned_to": 99999}, headers=manager_headers
    )
    assert resp.status_code == 404


def test_member_sees_only_own_tasks_in_list(client, manager_headers, member_headers):
    project_id, member_id = _setup_project_with_member(client, manager_headers, member_headers)
    client.post(
        "/tasks",
        json={"title": "Mine", "assigned_to": member_id, "project_id": project_id},
        headers=manager_headers,
    )
    client.post(
        "/tasks",
        json={"title": "NotMine", "project_id": project_id},
        headers=manager_headers,
    )

    resp = client.get("/tasks", headers=member_headers)
    body = resp.json()
    titles = [t["title"] for t in body["items"]]
    assert "Mine" in titles
    assert "NotMine" not in titles


def test_task_comment_and_attachment_flow(client, manager_headers, member_headers):
    project_id, member_id = _setup_project_with_member(client, manager_headers, member_headers)
    task = client.post(
        "/tasks",
        json={"title": "Commentable", "assigned_to": member_id, "project_id": project_id},
        headers=manager_headers,
    ).json()

    resp = client.post(
        f"/tasks/{task['id']}/comments", json={"comment": "Looks good"}, headers=member_headers
    )
    assert resp.status_code == 201

    resp = client.get(f"/tasks/{task['id']}/comments", headers=member_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = client.post(
        f"/tasks/{task['id']}/attachments",
        files={"file": ("../notes.txt", b"hello", "text/plain")},
        headers=member_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["filename"] == "notes.txt"
