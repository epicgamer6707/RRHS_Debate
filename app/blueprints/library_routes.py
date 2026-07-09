"""Library backend — save and delete a user's cards.

The Library view itself is rendered by main.dashboard_library; these endpoints
handle the AJAX save (from the scraper) and delete (from the Library).
"""
from flask import Blueprint, request, jsonify, abort
from flask_login import login_required, current_user

from ..extensions import db
from ..models import SavedCard

bp = Blueprint("library", __name__, url_prefix="/library")


@bp.route("/save", methods=["POST"])
@login_required
def save():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()[:255]
    text = data.get("text") or ""
    html = data.get("html") or ""

    if not text and not html:
        return jsonify({"ok": False, "error": "Nothing to save"}), 400

    card = SavedCard(user_id=current_user.id, title=title, text=text, html=html)
    db.session.add(card)
    db.session.commit()
    return jsonify({"ok": True, "id": card.id})


@bp.route("/<int:card_id>/delete", methods=["POST"])
@login_required
def delete(card_id):
    card = db.session.get(SavedCard, card_id)
    if card is None or card.user_id != current_user.id:
        abort(404)
    db.session.delete(card)
    db.session.commit()
    return jsonify({"ok": True})
