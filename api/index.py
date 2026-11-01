import os
import sys
import traceback
from pathlib import Path
from flask import Flask, request, jsonify

# Add project root directory to sys.path so 'app' and 'config' can be imported
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from app import create_app
    from app.extensions import db

    # Vercel requires 'app' to be an instance of Flask (hasattr wsgi_app)
    app = create_app(os.getenv("FLASK_ENV", "production"))

    # Add a zero-dependency health endpoint for instant diagnostic verification
    @app.route("/api/health")
    def health_check():
        db_configured = bool(os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL"))
        return jsonify({
            "status": "online",
            "service": "Personal Money Flow Tracker",
            "python_version": sys.version,
            "database_configured": db_configured,
        })

    # Lazy initialization flag: run once on first incoming HTTP request, NEVER during cold-start module load
    _db_initialized = False

    @app.before_request
    def lazy_db_init():
        global _db_initialized
        # Skip DB check on health probe and static assets to prevent timeouts
        if request.path in ("/api/health", "/manifest.json", "/sw.js") or request.path.startswith("/static"):
            return None

        if not _db_initialized:
            _db_initialized = True
            if os.getenv("AUTO_INIT_DB", "true").lower() in ("true", "1", "yes"):
                try:
                    db.create_all()
                except Exception as ex:
                    app.logger.warning(f"Database auto-init notice: {ex}")

except Exception:
    err_trace = traceback.format_exc()

    # Create a fallback Flask instance so Vercel's WSGI detection NEVER fails with 500 FUNCTION_INVOCATION_FAILED
    app = Flask(__name__)

    @app.route("/api/health")
    def fallback_health():
        return jsonify({"status": "error", "error": err_trace}), 500

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def startup_error_view(path):
        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Application Startup Error - Personal Money Flow Tracker</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem;">
  <div style="max-width: 800px; margin: 0 auto; background: #1e293b; border-radius: 12px; padding: 2rem; border: 1px solid #ef4444;">
    <h2 style="color: #ef4444; margin-top: 0;">Server Startup Diagnostics</h2>
    <p style="color: #94a3b8;">A startup error occurred while initializing the Flask application on Vercel:</p>
    <pre style="background: #090d16; color: #f87171; padding: 1.25rem; border-radius: 8px; overflow-x: auto; font-size: 0.875rem;">{err_trace}</pre>
    <p style="color: #94a3b8; font-size: 0.85rem;">Check your Vercel Environment Variables: DATABASE_URL and SECRET_KEY.</p>
  </div>
</body>
</html>"""
        return html, 500
