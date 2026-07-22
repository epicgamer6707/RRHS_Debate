"""Public Logs page: a shared to-do list + the changelog from GitHub.

No login required — anyone (signed in or not) can read the log and tick off todos.
"""
from flask import Blueprint, render_template, request, jsonify, abort

from ..extensions import db
from ..models import TodoItem
from ..changelog import get_updates

bp = Blueprint("logs", __name__)


@bp.route("/logs")
def logs():
    updates, err = get_updates()
    todos = TodoItem.query.order_by(TodoItem.created_at.asc()).all()
    return render_template("logs.html", updates=updates, changelog_error=err, todos=todos)


@bp.route("/logs/todo/add", methods=["POST"])
def todo_add():
    text = ((request.get_json(silent=True) or {}).get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "Type something first."}), 400
    item = TodoItem(text=text[:300])
    db.session.add(item)
    db.session.commit()
    return jsonify({"ok": True, "id": item.id, "text": item.text})


@bp.route("/logs/todo/<int:item_id>/done", methods=["POST"])
def todo_done(item_id):
    item = db.session.get(TodoItem, item_id)
    if item is None:
        abort(404)
    db.session.delete(item)   # checking it off removes it
    db.session.commit()
    return jsonify({"ok": True})
