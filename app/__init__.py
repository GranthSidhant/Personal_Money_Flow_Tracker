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
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(people_bp)
    app.register_blueprint(funds_bp)
    app.register_blueprint(receipts_bp)
    app.register_blueprint(bank_accounts_bp)
    app.register_blueprint(bank_transactions_bp)

    # Context processors for templates
    @app.context_processor
    def inject_utilities():
        return {
            "format_inr": format_inr,
            "app_name": "Personal Money Flow Tracker",
        }

    # Error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template("errors/500.html"), 500

    return app
