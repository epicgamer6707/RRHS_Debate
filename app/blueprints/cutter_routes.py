"""Card Cutter backend — cut a card from a URL, pasted text, or uploaded file.

Saving reuses the existing /library/save endpoint, so there's nothing to add
here for persistence.
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required

from ..cutter import extract_from_url, extract_from_file, cut_card

bp = Blueprint("cutter", __name__, url_prefix="/cutter")

_MAX_FILE = 8 * 1024 * 1024  # 8 MB


@bp.route("/cut", methods=["POST"])
@login_required
def cut():
    query = (request.form.get("query") or "").strip()
    if not query:
        return jsonify({"ok": False, "error": "Type what card you want first."}), 400

    upload = request.files.get("file")
    url = (request.form.get("url") or "").strip()
    pasted = (request.form.get("text") or "").strip()

    try:
        if upload and upload.filename:
            raw = upload.read(_MAX_FILE + 1)
            if len(raw) > _MAX_FILE:
                return jsonify({"ok": False, "error": "File is too large (8 MB max)."}), 400
            text = extract_from_file(upload.filename, raw)
            meta = {"text": text, "title": upload.filename, "author": "", "date": "",
                    "source": "Uploaded file", "url": ""}
        elif url:
            meta = extract_from_url(url)
            if meta is None:
                return jsonify({"ok": False, "error": "Couldn't fetch that URL."}), 400
        elif pasted:
            meta = {"text": pasted, "title": "", "author": "", "date": "",
                    "source": "Pasted text", "url": ""}
        else:
            return jsonify({"ok": False, "error": "Add a URL, paste text, or upload a file."}), 400
    except Exception as e:  # noqa: BLE001 — surface extraction failures to the user
        return jsonify({"ok": False, "error": f"Couldn't read that source: {e}"}), 400

    result = cut_card(meta, query)
    return jsonify(result), (200 if result.get("ok") else 400)


@bp.route("/extract", methods=["POST"])
@login_required
def extract():
    """Return the plain text of a source (for the Analyzer / Bot)."""
    upload = request.files.get("file")
    url = (request.form.get("url") or "").strip()
    pasted = (request.form.get("text") or "").strip()
    try:
        if upload and upload.filename:
            raw = upload.read(_MAX_FILE + 1)
            if len(raw) > _MAX_FILE:
                return jsonify({"ok": False, "error": "File is too large (8 MB max)."}), 400
            text = extract_from_file(upload.filename, raw)
        elif url:
            meta = extract_from_url(url)
            text = (meta or {}).get("text", "") if meta else ""
            if not text:
                return jsonify({"ok": False, "error": "Couldn't read that URL. Paste the text instead."}), 400
        elif pasted:
            text = pasted
        else:
            return jsonify({"ok": False, "error": "Add a URL, paste text, or upload a file."}), 400
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"Couldn't read that source: {e}"}), 400

    text = (text or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "No readable text found."}), 400
    return jsonify({"ok": True, "text": text[:12000]})
