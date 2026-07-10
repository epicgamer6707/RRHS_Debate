"""Citation Maker backend — turn a website link into citation fields.

The citation string itself is assembled live in the browser so the user can edit
every field; this endpoint just fills what it can from the page metadata.
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required

from ..cutter import extract_from_url
from ..citation import citation_fields

bp = Blueprint("citation", __name__, url_prefix="/citation")


@bp.route("/fetch", methods=["POST"])
@login_required
def fetch():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "Paste a website link first."}), 400

    meta = extract_from_url(url)
    if not meta:
        return jsonify({"ok": False, "error": "Couldn't fetch that link. Enter the details manually."}), 400

    return jsonify({"ok": True, **citation_fields(meta)})
