"""Competition signup backend.

For now this only exposes the Tabroom scrape endpoint so the UI can confirm the
tournament details. The "send to officers" step (Slack) comes later.
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from ..scraper.tabroom import scrape_tournament
from ..slack import send_signup_notification

bp = Blueprint("competition", __name__, url_prefix="/competition")


@bp.route("/scrape", methods=["POST"])
@login_required
def scrape():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "Paste a Tabroom tournament link first."}), 400

    result = scrape_tournament(url)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@bp.route("/send", methods=["POST"])
@login_required
def send():
    data = request.get_json(silent=True) or {}
    signup = {
        "name": (data.get("name") or "").strip(),
        "date": (data.get("date") or "").strip(),
        "location": (data.get("location") or "").strip(),
        "event": (data.get("event") or "").strip(),
        "url": (data.get("url") or "").strip(),
    }
    if not signup["name"] or not signup["event"]:
        return jsonify({"ok": False, "error": "Missing tournament name or event."}), 400

    delivered = send_signup_notification(current_user, signup)
    return jsonify({"ok": True, "delivered": delivered})
