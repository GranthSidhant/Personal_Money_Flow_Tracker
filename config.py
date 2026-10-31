import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the repository
BASE_DIR = Path(__file__).resolve().parent

# Load .env file if it exists
load_dotenv(BASE_DIR / ".env")


class Config:
    """Base application configuration."""
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-secret-key-change-in-production")
    
    # Handle PostgreSQL URL scheme fix for SQLAlchemy 2.0 (postgres:// -> postgresql://)
    # Check DATABASE_URL, POSTGRES_URL (Vercel Postgres / Neon integration), or POSTGRES_URL_NON_POOLING
    raw_db_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_URL")
        or os.getenv("POSTGRES_URL_NON_POOLING")
    )
    if raw_db_url and raw_db_url.startswith("postgres://"):
        raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)
    if raw_db_url and "sslmode=" not in raw_db_url and any(h in raw_db_url for h in ("neon.tech", "vercel-storage.com", "supabase.co", "render.com")):
        raw_db_url += ("&" if "?" in raw_db_url else "?") + "sslmode=require"

    # If raw_db_url is postgresql://, verify if psycopg2 is available; otherwise fallback to pure-python pg8000
    if raw_db_url and raw_db_url.startswith("postgresql://"):
        try:
            import psycopg2  # noqa
        except Exception:
            try:
                import pg8000  # noqa
                raw_db_url = raw_db_url.replace("postgresql://", "postgresql+pg8000://", 1)
            except Exception:
                pass

    database_url = raw_db_url

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
