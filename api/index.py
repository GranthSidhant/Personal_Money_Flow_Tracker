import os
import sys
from pathlib import Path

# Add project root directory to sys.path so 'app' and 'config' can be imported
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.extensions import db

# In serverless environments, default to production config
environment = os.getenv("FLASK_ENV", "production")
app = create_app(environment)

# Automatic idempotent schema creation for fresh databases (Neon / Vercel Postgres / Supabase)
# Automatically creates any missing tables on first startup
if os.getenv("AUTO_INIT_DB", "true").lower() in ("true", "1", "yes"):
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            app.logger.warning(f"Database auto-init notice: {e}")
