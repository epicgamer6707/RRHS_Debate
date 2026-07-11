"""Application factory."""
import os
import time

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import db, login_manager, oauth, csrf

# Changes every process start (i.e. every deploy) → appended to static URLs so
# browsers fetch fresh CSS/JS after a deploy instead of serving a stale cache.
ASSET_VERSION = str(int(time.time()))


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    # Cache-bust static assets: url_for('static', filename=…) gets ?v=ASSET_VERSION.
    @app.url_defaults
    def _static_cache_bust(endpoint, values):
        if endpoint == "static" and "filename" in values:
            values.setdefault("v", ASSET_VERSION)

    # Behind Railway's proxy: trust X-Forwarded-Proto/Host so url_for(_external=True)
    # builds https:// URLs (needed for the Google OAuth redirect URI to match).
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

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
        # Separate offline client for the Google Classroom Resources feed.
        # (access_type/prompt are passed on authorize_redirect, not here, so they
        # actually reach Google's authorization URL and yield a refresh token.)
        oauth.register(
            name="gclass",
            client_id=app.config["GOOGLE_CLIENT_ID"],
            client_secret=app.config["GOOGLE_CLIENT_SECRET"],
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": " ".join(app.config["CLASSROOM_SCOPES"])},
        )

    # Make the Google flag available to every template.
    @app.context_processor
    def inject_flags():
        return {"google_enabled": app.config.get("GOOGLE_ENABLED", False)}

    # Register blueprints.
    from .blueprints.scraper_routes import bp as scraper_bp
    from .blueprints.main_routes import bp as main_bp
    from .blueprints.library_routes import bp as library_bp
    from .blueprints.competition_routes import bp as competition_bp
    from .blueprints.cutter_routes import bp as cutter_bp
    from .blueprints.citation_routes import bp as citation_bp
    from .blueprints.resources_routes import bp as resources_bp
    from .auth.routes import bp as auth_bp
    app.register_blueprint(scraper_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(library_bp)
    app.register_blueprint(competition_bp)
    app.register_blueprint(cutter_bp)
    app.register_blueprint(citation_bp)
    app.register_blueprint(resources_bp)
    app.register_blueprint(auth_bp)

    # Create tables on first boot (fine for now; we'll switch to migrations later).
    with app.app_context():
        # Import models so SQLAlchemy knows about the tables before create_all.
        from . import models  # noqa: F401
        db.create_all()

    return app
