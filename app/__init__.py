"""Application factory."""
import os

from flask import Flask

from .config import Config
from .extensions import db


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)

    # Register blueprints.
    from .blueprints.scraper_routes import bp as scraper_bp
    app.register_blueprint(scraper_bp)

    # Create tables on first boot (fine for now; we'll switch to migrations later).
    with app.app_context():
        # Import models so SQLAlchemy knows about the tables before create_all.
        from . import models  # noqa: F401
        db.create_all()

    return app
