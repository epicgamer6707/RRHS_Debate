"""Shared Flask extension instances.

Kept in their own module so both the app factory and the models/blueprints can
import them without creating circular imports.
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
