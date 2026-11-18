"""Authentication: login, token validation, and route protection."""

from app.auth.security import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    create_access_token,
    hash_password,
    verify_password,
)


# --- route protection -----------------------------------------------------

def test_health_check_stays_public(anonymous_client):
    response = anonymous_client.get("/api/health")

    assert response.status_code == 200


def test_business_routes_require_a_token(anonymous_client):
    for path in ("/api/documents", "/api/accounts", "/api/reports/trial-balance"):
        response = anonymous_client.get(path)
        assert response.status_code == 401, path
        assert response.headers.get("www-authenticate") == "Bearer"


def test_a_garbage_token_is_rejected(anonymous_client):
    response = anonymous_client.get(
        "/api/documents", headers={"Authorization": "Bearer not-a-real-token"}
    )

    assert response.status_code == 401


def test_an_expired_token_is_rejected(anonymous_client):
    login = anonymous_client.post(
        "/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    anonymous_client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    user_id = anonymous_client.get("/api/auth/me").json()["id"]

    expired = create_access_token(user_id, ADMIN_EMAIL, expires_minutes=-1)
    response = anonymous_client.get(
        "/api/documents", headers={"Authorization": f"Bearer {expired}"}
    )

    assert response.status_code == 401


# --- login ----------------------------------------------------------------

def test_login_returns_a_bearer_token(anonymous_client):
    response = anonymous_client.post(
        "/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == ADMIN_EMAIL


def test_login_rejects_a_wrong_password(anonymous_client):
    response = anonymous_client.post(
        "/api/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong-password"}
    )

    assert response.status_code == 401


def test_login_rejects_an_unknown_email(anonymous_client):
    response = anonymous_client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": ADMIN_PASSWORD}
    )

    assert response.status_code == 401


def test_email_lookup_is_case_insensitive(anonymous_client):
    response = anonymous_client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL.upper(), "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 200


# --- token contents -------------------------------------------------------

def test_me_returns_the_signed_in_user(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == ADMIN_EMAIL
    assert response.json()["role"] == "ADMIN"


def test_password_is_hashed_not_stored_plain(anonymous_client):
    hashed = hash_password("secret-value")

    assert hashed != "secret-value"
    assert hashed.startswith("$2")
    assert verify_password("secret-value", hashed) is True
    assert verify_password("other-value", hashed) is False


# --- audit ----------------------------------------------------------------

def test_login_is_written_to_the_audit_trail(client):
    logs = client.get("/api/reports/audit-logs").json()

    assert any(log["action"] == "LOGIN" for log in logs)
