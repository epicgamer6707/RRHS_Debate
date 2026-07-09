"""Compatibility shim.

Railway's service Start Command is still `python haku_extractor.py` (set before
the Phase 1 restructure). This file just launches the real app defined in
wsgi.py / the app/ package, so the old command keeps working.

Safe to delete once the Railway Start Command is cleared (Service → Settings →
Deploy → Start Command), which lets it fall back to the Dockerfile's
`CMD ["python", "wsgi.py"]`.
"""
import os

from wsgi import app
from app.scraper import ensure_pw_thread

if __name__ == "__main__":
    ensure_pw_thread()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)
