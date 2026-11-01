import os
from flask import Flask, render_template
from config import config_by_name
from app.extensions import db, migrate, login_manager, csrf
from app.utils.money import format_inr


def create_app(config_name: str = None) -> Flask:
    """Application factory for Personal Money Flow Tracker."""
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")
        
    app = Flask(__name__)
    config_class = config_by_name.get(config_name, config_by_name["default"])
    app.config.from_object(config_class)

    # Dynamically sanitize and re-apply DATABASE_URL from runtime environment
    from config import clean_database_url
    raw_env = (
        os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_URL")
        or os.getenv("POSTGRES_URL_NON_POOLING")
    )
    if raw_env:
        cleaned_db = clean_database_url(raw_env)
        if cleaned_db:
            app.config["SQLALCHEMY_DATABASE_URI"] = cleaned_db

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.people import people_bp
    from app.routes.funds import funds_bp
    from app.routes.receipts import receipts_bp
    from app.routes.bank_accounts import bank_accounts_bp
    from app.routes.bank_transactions import bank_transactions_bp
    from app.routes.expenses import expenses_bp
    from app.routes.pocket_money import pocket_money_bp
    from app.routes.settlements import settlements_bp
    from app.routes.reports import reports_bp
    from app.routes.voice_notes import voice_notes_bp
    from app.routes.sync import sync_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(people_bp)
    app.register_blueprint(funds_bp)
    app.register_blueprint(receipts_bp)
    app.register_blueprint(bank_accounts_bp)
    app.register_blueprint(bank_transactions_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(pocket_money_bp)
    app.register_blueprint(settlements_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(voice_notes_bp)
    app.register_blueprint(sync_bp)

    # Context processors for templates
    @app.context_processor
    def inject_utilities():
        return {
            "format_inr": format_inr,
            "app_name": "Personal Money Flow Tracker",
        }

    # Security headers
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # Error handlers with resilient fallbacks for serverless deployments
    @app.errorhandler(404)
    def page_not_found(e):
        try:
            return render_template("errors/404.html"), 404
        except Exception:
            return "<h1>404 Not Found</h1>", 404

    @app.errorhandler(403)
    def forbidden(e):
        try:
            return render_template("errors/403.html"), 403
        except Exception:
            return "<h1>403 Forbidden</h1>", 403

    @app.errorhandler(500)
    def internal_server_error(e):
        import traceback
        tb = traceback.format_exc()
        app.logger.error(f"500 Internal Error: {e}\n{tb}")
        try:
            return render_template("errors/500.html"), 500
        except Exception:
            return (
                f"<!DOCTYPE html><html><head><title>500 Internal Error</title></head>"
                f"<body style='font-family:-apple-system,sans-serif;padding:2rem;background:#0f172a;color:#f8fafc;'>"
                f"<h1 style='color:#ef4444;'>500 Server Error</h1>"
                f"<p>{e}</p><pre style='background:#1e293b;padding:1rem;border-radius:8px;color:#f87171;overflow:auto;'>{tb}</pre>"
                f"</body></html>",
                500,
            )

    return app
