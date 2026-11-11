import os
import sys
from app import create_app
from app.extensions import db

# WSGI application entrypoint for Gunicorn, Docker, and Vercel serverless runtime
environment = os.getenv("FLASK_ENV", "production")
app = create_app(environment)
application = app  # Standard WSGI callable alias for serverless runtimes

# Lazy DB initialization on first request
_db_initialized = False

@app.before_request
def auto_init_db_once():
    global _db_initialized
    from flask import request
    if request.path.startswith("/api/health") or request.path.startswith("/static"):
        return None
    if not _db_initialized:
        _db_initialized = True
        if os.getenv("AUTO_INIT_DB", "true").lower() in ("true", "1", "yes"):
            try:
                db.create_all()
            except Exception as e:
                app.logger.warning(f"AUTO_INIT_DB notice: {e}")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
