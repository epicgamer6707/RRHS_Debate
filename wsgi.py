"""Entry point.

Local dev:   python wsgi.py
Production:  gunicorn wsgi:app   (Railway)
"""
import os

from app import create_app
from app.scraper import ensure_pw_thread

app = create_app()

# Start the Card Finder's browser eagerly so the first search isn't slow. Runs
# whether the app is launched directly (python wsgi.py) or imported by gunicorn.
ensure_pw_thread()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)
