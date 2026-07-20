def test_signup_success(client):
    resp = client.post(
        "/auth/signup",
        json={
            "full_name": "Jane Doe",
            "email": "jane@example.com",
            "password": "password123",
            "role": "member",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "jane@example.com"
    assert "password" not in data


def test_signup_duplicate_email_rejected(client):
    payload = {
        "full_name": "Jane Doe",
        "email": "dup@example.com",
        "password": "password123",
        "role": "member",
    }
    client.post("/auth/signup", json=payload)
    resp = client.post("/auth/signup", json=payload)
    assert resp.status_code == 400


def test_login_wrong_password_rejected(client):
    client.post(
        "/auth/signup",
        json={
            "full_name": "Jane Doe",
            "email": "jane2@example.com",
            "password": "password123",
            "role": "member",
        },
    )
    resp = client.post(
        "/auth/login", data={"username": "jane2@example.com", "password": "wrongpass"}
    )
    assert resp.status_code == 401


def test_me_requires_token(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user(client, member_headers):
    resp = client.get("/auth/me", headers=member_headers)
    assert resp.status_code == 200
    assert resp.json()["role"] == "member"


def test_malformed_token_subject_is_rejected(client):
    from app.security import create_access_token

    token = create_access_token({"sub": "not-an-int"})
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
