import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the repository
BASE_DIR = Path(__file__).resolve().parent

# Load .env file if it exists
load_dotenv(BASE_DIR / ".env")


import re
from sqlalchemy.engine import make_url


def clean_database_url(raw_url: str | None) -> str | None:
    """
    Sanitize database URLs to prevent SQLAlchemy ArgumentError.
    Handles quotes, psql command wrappers, assignment syntax, and URL scheme normalization.
    """
    if not raw_url:
        return None

    url = str(raw_url).strip().strip('"').strip("'").strip()
    if not url or url.lower() in ("none", "null", "undefined"):
        return None

    # Search for an embedded postgresql://, postgres://, or sqlite:/// URI
    match = re.search(r"((?:postgres(?:ql)?|sqlite)://[^\s'\"]+)", url)
    if match:
        url = match.group(1).rstrip("'\"")

    # SQLAlchemy 2.0 requires postgresql:// instead of postgres://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    # Automatically attach sslmode=require for common managed PostgreSQL clouds
    if url.startswith("postgresql://") and "sslmode=" not in url:
        if any(h in url for h in ("neon.tech", "vercel-storage.com", "supabase.co", "render.com", "aws")):
            url += ("&" if "?" in url else "?") + "sslmode=require"

    # Fallback to pure-Python pg8000 if psycopg2 is missing
    if url.startswith("postgresql://"):
        try:
            import psycopg2  # noqa
        except Exception:
            try:
                import pg8000  # noqa
                url = url.replace("postgresql://", "postgresql+pg8000://", 1)
            except Exception:
                pass

    # Verify that SQLAlchemy can parse it safely
    try:
        make_url(url)
        return url
    except Exception as ex:
        print(f"[WARNING] Database URL validation failed: {ex}. Falling back to SQLite.")
        return None


class Config:
    """Base application configuration."""
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-secret-key-change-in-production")

    # Clean and validate cloud PostgreSQL URI
    raw_env_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_URL")
        or os.getenv("POSTGRES_URL_NON_POOLING")
    )
    database_url = clean_database_url(raw_env_url)

    # Instance directory (safe fallback for serverless read-only environments like Vercel Lambda)
    instance_dir = BASE_DIR / "instance"
    try:
        instance_dir.mkdir(exist_ok=True)
    except OSError:
        instance_dir = Path("/tmp/instance")
        try:
            instance_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

    SQLALCHEMY_DATABASE_URI = database_url or f"sqlite:///{instance_dir / 'money_tracker.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session and security cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Upload and media storage (safe for local dev, container, and serverless /tmp)
    upload_env = os.getenv("UPLOAD_FOLDER")
    if upload_env:
        UPLOAD_FOLDER = Path(upload_env)
    elif os.getenv("VERCEL"):
        UPLOAD_FOLDER = Path("/tmp/uploads")
    else:
        UPLOAD_FOLDER = BASE_DIR / "uploads"

    try:
        UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    except OSError:
        UPLOAD_FOLDER = Path("/tmp/uploads")
        try:
            UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))  # 16 MB max


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    """Testing configuration with in-memory SQLite and CSRF disabled."""
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret-key"


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
