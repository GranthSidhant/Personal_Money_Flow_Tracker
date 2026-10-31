import pytest
from app import create_app
from app.extensions import db
from app.models.user import User


@pytest.fixture
def app():
    """Create and configure a Flask application for testing."""
    application = create_app("testing")

    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """A test client for the application."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """A test CLI runner for the application."""
    return app.test_cli_runner()


@pytest.fixture
def sample_user(app):
    """Create and return a sample registered user."""
    with app.app_context():
        user = User(name="Test User", email="test@example.com")
        user.set_password("SecurePassword123!")
        db.session.add(user)
        db.session.commit()
        # Return user id so tests can fetch in their own context
        return user.id


@pytest.fixture
def sample_user_b(app):
    """Create and return a second sample user for isolation tests."""
    with app.app_context():
        user = User(name="User Two", email="user2@example.com")
        user.set_password("AnotherPassword456!")
        db.session.add(user)
        db.session.commit()
        return user.id
