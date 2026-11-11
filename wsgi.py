import os
import sys

# WSGI application entrypoint for Gunicorn, Docker, and Vercel serverless runtime
environment = os.getenv("FLASK_ENV", "production")

try:
    from app import create_app
    from app.extensions import db

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

except Exception as startup_err:
    import traceback
    startup_traceback = traceback.format_exc()
    try:
        from flask import Flask, jsonify

        # Safe fallback Flask app so Vercel does not crash with an opaque 500 error
        app = Flask(__name__)

        @app.route("/api/health")
        def health_fallback():
            return jsonify({
                "status": "error",
                "service": "Personal Money Flow Tracker",
                "message": "Flask application failed during startup initialization",
                "error": str(startup_err),
                "traceback": startup_traceback,
            }), 500

        @app.route("/", defaults={"path": ""})
        @app.route("/<path:path>")
        def fallback_view(path):
            return (
                f"<!DOCTYPE html><html><head><title>Startup Error - 500</title></head>"
                f"<body style='font-family:-apple-system,sans-serif;padding:2rem;background:#0f172a;color:#f8fafc;'>"
                f"<h1 style='color:#ef4444;'>Application Startup Error</h1>"
                f"<p>The application encountered an error while starting up on Vercel:</p>"
                f"<pre style='background:#1e293b;padding:1rem;border-radius:8px;color:#f87171;overflow:auto;'>{startup_traceback}</pre>"
                f"</body></html>",
                500,
            )
        application = app
    except Exception:
        # Zero-dependency raw WSGI fallback if even Flask fails to import
        def raw_wsgi_app(environ, start_response):
            start_response('500 Internal Server Error', [('Content-Type', 'text/html; charset=utf-8')])
            return [f"<h1>500 Startup Error</h1><pre>{startup_traceback}</pre>".encode('utf-8')]
        app = raw_wsgi_app
        application = raw_wsgi_app

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
