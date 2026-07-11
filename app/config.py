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

    # Email (Resend) — used for password-reset links.
    RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
    # Resend gives everyone onboarding@resend.dev for testing without a domain.
    MAIL_FROM = os.environ.get("MAIL_FROM", "RRHS Debate <onboarding@resend.dev>").strip()
    EMAIL_ENABLED = bool(RESEND_API_KEY)

    # Slack — incoming webhook for the officers' channel (competition signups).
    SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    SLACK_ENABLED = bool(SLACK_WEBHOOK_URL)

    # Officers (comma-separated emails) may post to the Classroom. If unset,
    # everyone can post — set this in Railway to lock posting to officers.
    OFFICER_EMAILS = [
        e.strip().lower() for e in os.environ.get("OFFICER_EMAILS", "").split(",") if e.strip()
    ]

    # Supabase Storage for Classwork documents. Uses the service_role key (never
    # exposed to the browser) so the bucket can stay private; downloads go out
    # through short-lived signed URLs generated per request.
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "classroom-files").strip()
    STORAGE_ENABLED = bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)
