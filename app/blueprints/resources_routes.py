"""Resources backend — connect Google Classroom and serve its feed."""
from flask import Blueprint, redirect, url_for, jsonify, current_app, request
from flask_login import login_required

from ..extensions import oauth
from ..google_classroom import save_auth, clear_auth, get_feed, is_connected, connected_email

bp = Blueprint("resources", __name__, url_prefix="/resources")


@bp.route("/connect")
@login_required
def connect():
    if not current_app.config.get("GOOGLE_ENABLED"):
        return redirect(url_for("main.dashboard_resources"))
    redirect_uri = url_for("resources.connect_callback", _external=True)
    return oauth.gclass.authorize_redirect(redirect_uri)


@bp.route("/connect/callback")
@login_required
def connect_callback():
    if not current_app.config.get("GOOGLE_ENABLED"):
        return redirect(url_for("main.dashboard_resources"))
    try:
        token = oauth.gclass.authorize_access_token()
    except Exception:
        return redirect(url_for("main.dashboard_resources", error="failed"))

    refresh = token.get("refresh_token")
    email = (token.get("userinfo") or {}).get("email", "")
    if not refresh:
        # No offline grant — usually means "Allow" wasn't fully approved.
        return redirect(url_for("main.dashboard_resources", error="offline"))

    save_auth(refresh, email)
    return redirect(url_for("main.dashboard_resources", connected="1"))


@bp.route("/disconnect", methods=["POST"])
@login_required
def disconnect():
    clear_auth()
    return jsonify({"ok": True})


@bp.route("/data")
@login_required
def data():
    return jsonify(get_feed(force=request.args.get("force") == "1"))
