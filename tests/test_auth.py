from app.models.user import User
from app.extensions import db


def test_registration_success(client, app):
    """Verify that a new user can register and their password is encrypted."""
    response = client.post(
        "/auth/register",
        data={
            "name": "Jane Doe",
            "email": "jane@example.com",
            "password": "Password1234!",
            "confirm_password": "Password1234!",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Welcome to Personal Money Flow Tracker" in response.data or b"Dashboard" in response.data

    with app.app_context():
        user = User.query.filter_by(email="jane@example.com").first()
        assert user is not None
        assert user.name == "Jane Doe"
        # Password must be hashed, never plain text
        assert user.password_hash != "Password1234!"
        assert user.check_password("Password1234!")


def test_registration_duplicate_email(client, sample_user):
    """Verify that registering with an existing email fails."""
    response = client.post(
        "/auth/register",
        data={
            "name": "Duplicate User",
            "email": "test@example.com",
            "password": "Password1234!",
            "confirm_password": "Password1234!",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"An account with this email address already exists" in response.data


def test_registration_password_mismatch(client):
    """Verify registration fails when confirmation password doesn't match."""
    response = client.post(
        "/auth/register",
        data={
            "name": "Mismatch User",
            "email": "mismatch@example.com",
            "password": "Password1234!",
            "confirm_password": "DifferentPassword1!",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Passwords must match" in response.data


def test_login_success(client, sample_user):
    """Verify that a registered user can log in with valid credentials."""
    response = client.post(
        "/auth/login",
        data={
            "email": "test@example.com",
            "password": "SecurePassword123!",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Welcome back!" in response.data
    assert b"Dashboard" in response.data


def test_login_invalid_password(client, sample_user):
    """Verify that login fails with an incorrect password."""
    response = client.post(
        "/auth/login",
        data={
            "email": "test@example.com",
            "password": "WrongPassword!",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Invalid email or password" in response.data


def test_logout(client, sample_user):
    """Verify that a user can log out successfully."""
    # First login
    client.post(
        "/auth/login",
        data={
            "email": "test@example.com",
            "password": "SecurePassword123!",
        },
        follow_redirects=True,
    )
    # Then logout
    response = client.get("/auth/logout", follow_redirects=True)
    assert response.status_code == 200
    assert b"You have been successfully logged out" in response.data


def test_change_password(client, app, sample_user):
    """Verify that an authenticated user can change their password."""
    client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "SecurePassword123!"},
        follow_redirects=True,
    )

    response = client.post(
        "/auth/change-password",
        data={
            "current_password": "SecurePassword123!",
            "new_password": "BrandNewPassword999!",
            "confirm_new_password": "BrandNewPassword999!",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Your password has been updated successfully" in response.data

    with app.app_context():
        user = db.session.get(User, sample_user)
        assert user.check_password("BrandNewPassword999!")
        assert not user.check_password("SecurePassword123!")


def test_profile_update(client, app, sample_user):
    """Verify that user can update profile details."""
    client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "SecurePassword123!"},
        follow_redirects=True,
    )

    response = client.post(
        "/auth/profile",
        data={"name": "Updated Name"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Your profile details have been updated" in response.data

    with app.app_context():
        user = db.session.get(User, sample_user)
        assert user.name == "Updated Name"
