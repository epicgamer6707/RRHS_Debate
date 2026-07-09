"""Application factory."""
import os

from flask import Flask

from .config import Config
from .extensions import db, login_manager


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    login_manager.init_app(app)

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
