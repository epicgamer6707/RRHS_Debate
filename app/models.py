"""Database models.

These tables are scaffolding for later phases:
  * User      — accounts (email/password + Google sign-in), used in Phase 2.
  * SavedCard — cards a user saves from the scraper, used in Phase 5 (Library).
"""
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from .extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False, default="")

    # Null when the account was created via Google (no local password).
    password_hash = db.Column(db.String(255), nullable=True)
    # Google account id ("sub"), null for password-only accounts.
    google_id = db.Column(db.String(255), unique=True, nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    saved_cards = db.relationship(
        "SavedCard", backref="user", lazy=True, cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.email}>"


class SavedCard(db.Model):
    __tablename__ = "saved_cards"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    title = db.Column(db.String(255), nullable=False, default="")
    text = db.Column(db.Text, nullable=False, default="")
    html = db.Column(db.Text, nullable=False, default="")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<SavedCard {self.title[:40]!r}>"
