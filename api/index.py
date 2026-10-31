import os
import sys
import traceback
from pathlib import Path

# Add project root directory to sys.path so 'app' and 'config' can be imported
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

flask_app = None
init_error = None

try:
    from app import create_app
    from app.extensions import db

    environment = os.getenv("FLASK_ENV", "production")
    flask_app = create_app(environment)

    # Lazy initialization flag: run once on first incoming HTTP request, NEVER during cold-start module load
    _db_checked = False

    @flask_app.before_request
    def lazy_db_init():
        global _db_checked
        if not _db_checked:
            _db_checked = True
            if os.getenv("AUTO_INIT_DB", "true").lower() in ("true", "1", "yes"):
                try:
                    db.create_all()
                except Exception as ex:
                    flask_app.logger.warning(f"Database auto-init notice: {ex}")

except Exception:
    init_error = traceback.format_exc()


def app(environ, start_response):
    """
    WSGI Entrypoint for Vercel Serverless Functions.
    Gracefully catches and displays initialization errors instead of silent 500 crash.
    """
    global flask_app, init_error

    if init_error:
        status = "500 Internal Server Error"
        response_headers = [("Content-Type", "text/html; charset=utf-8")]
        start_response(status, response_headers)
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
    <pre style="background: #090d16; color: #f87171; padding: 1.25rem; border-radius: 8px; overflow-x: auto; font-size: 0.875rem;">{init_error}</pre>
    <p style="color: #94a3b8; font-size: 0.85rem;">Check your Vercel Environment Variables: DATABASE_URL and SECRET_KEY.</p>
  </div>
</body>
</html>"""
        return [html.encode("utf-8")]

    try:
        return flask_app(environ, start_response)
    except Exception:
        req_error = traceback.format_exc()
        status = "500 Internal Server Error"
        response_headers = [("Content-Type", "text/html; charset=utf-8")]
        start_response(status, response_headers)
        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Request Execution Error</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem;">
  <div style="max-width: 800px; margin: 0 auto; background: #1e293b; border-radius: 12px; padding: 2rem; border: 1px solid #f59e0b;">
    <h2 style="color: #f59e0b; margin-top: 0;">Request Execution Error</h2>
    <p style="color: #94a3b8;">An unhandled error occurred during request handling:</p>
    <pre style="background: #090d16; color: #fbbf24; padding: 1.25rem; border-radius: 8px; overflow-x: auto; font-size: 0.875rem;">{req_error}</pre>
  </div>
</body>
</html>"""
        return [html.encode("utf-8")]
