"""Application factory."""
import os

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import db, login_manager, oauth


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    # Behind Railway's proxy: trust X-Forwarded-Proto/Host so url_for(_external=True)
    # builds https:// URLs (needed for the Google OAuth redirect URI to match).
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    login_manager.init_app(app)

    # Google OAuth — only registered when credentials are present.
    oauth.init_app(app)
    if app.config.get("GOOGLE_ENABLED"):
        oauth.register(
            name="google",
            client_id=app.config["GOOGLE_CLIENT_ID"],
            client_secret=app.config["GOOGLE_CLIENT_SECRET"],
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )

    # Make the Google flag available to every template.
    @app.context_processor
    def inject_flags():
        return {"google_enabled": app.config.get("GOOGLE_ENABLED", False)}

    # Register blueprints.
    from .blueprints.scraper_routes import bp as scraper_bp
    from .blueprints.main_routes import bp as main_bp
    from .auth.routes import bp as auth_bp
    app.register_blueprint(scraper_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)

    # Create tables on first boot (fine for now; we'll switch to migrations later).
    with app.app_context():
        # Import models so SQLAlchemy knows about the tables before create_all.
        from . import models  # noqa: F401
        db.create_all()

    return app
