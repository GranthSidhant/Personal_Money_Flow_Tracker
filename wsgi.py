import os
import sys
from flask import jsonify
from app import create_app
from app.extensions import db

# WSGI application entrypoint for Gunicorn, Docker, and Vercel serverless runtime
environment = os.getenv("FLASK_ENV", "production")
app = create_app(environment)

# Zero-dependency health endpoint for instant diagnostic verification
@app.route("/api/health")
def health_check():
    db_configured = bool(os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL"))
    return jsonify({
        "status": "online",
        "service": "Personal Money Flow Tracker",
        "python_version": sys.version,
        "database_configured": db_configured,
    })

# Lazy DB initialization on first request
_db_initialized = False

@app.before_request
def auto_init_db_once():
    global _db_initialized
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
