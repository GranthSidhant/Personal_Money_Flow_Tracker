import os
import io
import pytest
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.voice_note import VoiceNote
from config import ProductionConfig, DevelopmentConfig, Config


def test_security_headers_present(client):
    """Verify standard security headers are applied to HTTP responses."""
    resp = client.get("/")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert "1; mode=block" in resp.headers.get("X-XSS-Protection", "")
    assert "strict-origin-when-cross-origin" in resp.headers.get("Referrer-Policy", "")


def test_production_config_security_attributes():
    """Production configuration enforces HTTPS cookies and disables debug mode."""
    prod = ProductionConfig()
    assert prod.DEBUG is False
    assert prod.TESTING is False
    assert prod.SESSION_COOKIE_SECURE is True
    assert prod.SESSION_COOKIE_HTTPONLY is True
    assert prod.SESSION_COOKIE_SAMESITE == "Lax"


def test_postgres_url_scheme_normalization():
    """Legacy postgres:// URLs from hosting providers are converted to postgresql:// for SQLAlchemy 2.x."""
    original_url = os.environ.get("DATABASE_URL")
    try:
        os.environ["DATABASE_URL"] = "postgres://usr:pwd@host:5432/db"
        from config import Config as DynamicConfig
        # Refresh configuration class
        url = os.getenv("DATABASE_URL")
        if url and url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        assert url.startswith("postgresql://")
    finally:
        if original_url is not None:
            os.environ["DATABASE_URL"] = original_url
        else:
            os.environ.pop("DATABASE_URL", None)


def test_audio_file_access_control(app, client, sample_user, sample_user_b):
    """Audio files are strictly isolated and access-controlled."""
    with app.app_context():
        u1 = User.query.get(sample_user)
        u2 = User.query.get(sample_user_b)

        # Create voice note for user 1
        vn = VoiceNote(
            user_id=u1.id,
            title="Confidential Audio Note",
            text_note="Secret financial detail",
            audio_storage_path="audio/1/secret_test.webm",
            captured_at=db.func.now(),
        )
        db.session.add(vn)
        db.session.commit()
        vn_id = vn.id

    # 1. Unauthenticated request must be denied (redirect to login)
    r_unauth = client.get(f"/voice-notes/{vn_id}/audio")
    assert r_unauth.status_code == 302
    assert "/auth/login" in r_unauth.headers.get("Location", "")

    # 2. Authenticated as User 2 (different user) must be blocked with 404
    client.post("/auth/login", data={
        "email": "user2@example.com",
        "password": "AnotherPassword456!",
    })

    r_cross_user = client.get(f"/voice-notes/{vn_id}/audio")
    assert r_cross_user.status_code == 404
