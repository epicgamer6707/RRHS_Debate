"""Entry point.

Local dev:   python wsgi.py
Production:  gunicorn wsgi:app   (Railway)
"""
# Redeploy trigger — verifying Postgres persistence across deploys.
import os

from app import create_app
from app.scraper import ensure_pw_thread

app = create_app()

if __name__ == "__main__":
    ensure_pw_thread()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)
