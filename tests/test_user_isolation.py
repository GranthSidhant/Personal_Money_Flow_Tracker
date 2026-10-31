def test_unauthenticated_dashboard_redirects(client):
    """Protected routes must redirect unauthenticated visitors to login."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_unauthenticated_profile_redirects(client):
    """User profile must require authentication."""
    response = client.get("/auth/profile", follow_redirects=False)
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_authenticated_dashboard_access(client, sample_user):
    """Authenticated user must be able to view their dashboard."""
    client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "SecurePassword123!"},
        follow_redirects=True,
    )
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"Dashboard" in response.data
    assert b"Total Money In" in response.data


def test_user_session_isolation(client, app, sample_user, sample_user_b):
    """Ensure session of User A does not expose User B's profile details."""
    # Login as User A
    client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "SecurePassword123!"},
        follow_redirects=True,
    )

    response = client.get("/auth/profile")
    assert response.status_code == 200
    assert b"test@example.com" in response.data
    assert b"user2@example.com" not in response.data
