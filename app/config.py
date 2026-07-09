"""Application configuration.

Values are read from environment variables so the same code runs locally
(SQLite, defaults) and on Railway (Postgres, secrets set in the dashboard).
"""
import os


def _database_url():
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        # Local default: a SQLite file in the project root.
        return "sqlite:///" + os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.db"
        )
    # Railway/Heroku hand out "postgres://" but SQLAlchemy wants "postgresql://".
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Google OAuth (Authlib reads GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET).
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    # Only offer "Sign in with Google" once both credentials are configured.
    GOOGLE_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
