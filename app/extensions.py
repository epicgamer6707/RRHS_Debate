"""Shared Flask extension instances.

Kept in their own module so both the app factory and the models/blueprints can
import them without creating circular imports.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from authlib.integrations.flask_client import OAuth
from flask_wtf import CSRFProtect

db = SQLAlchemy()
oauth = OAuth()
csrf = CSRFProtect()

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please sign in to continue."
login_manager.login_message_category = "info"
