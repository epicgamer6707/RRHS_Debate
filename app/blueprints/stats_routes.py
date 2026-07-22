"""Dashboard stats — a user's debate record and per-tournament results."""
from flask import Blueprint, request, jsonify, abort
from flask_login import login_required, current_user

from ..extensions import db
from ..models import DebateRecord, TournamentResult
from ..tabroom_results import scrape_record

bp = Blueprint("stats", __name__, url_prefix="/stats")


def _record_for(user, create=False):
    rec = DebateRecord.query.filter_by(user_id=user.id).first()
    if rec is None and create:
        rec = DebateRecord(user_id=user.id)
        db.session.add(rec)
        db.session.flush()
    return rec


def _int(v, default=0):
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return default


@bp.route("/update", methods=["POST"])
@login_required
def update():
    data = request.get_json(silent=True) or {}
    rec = _record_for(current_user, create=True)
    rec.wins = _int(data.get("wins"), rec.wins)
    rec.losses = _int(data.get("losses"), rec.losses)
    rec.tabroom_url = (data.get("tabroom_url") or rec.tabroom_url or "").strip()[:600]
    db.session.commit()
    return jsonify({"ok": True, "wins": rec.wins, "losses": rec.losses})


@bp.route("/tournament", methods=["POST"])
@login_required
def add_tournament():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Tournament name is required."}), 400
    rec = _record_for(current_user, create=True)
    t = TournamentResult(
        record_id=rec.id, name=name[:255],
        date_str=(data.get("date") or "").strip()[:80],
        wins=_int(data.get("wins")), losses=_int(data.get("losses")),
        place=(data.get("place") or "").strip()[:80],
    )
    db.session.add(t)
    # Roll the tournament into the season totals.
    rec.wins += t.wins
    rec.losses += t.losses
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/tournament/<int:tid>/delete", methods=["POST"])
@login_required
def delete_tournament(tid):
    t = db.session.get(TournamentResult, tid)
    if t is None or t.record.user_id != current_user.id:
        abort(404)
    t.record.wins = max(0, t.record.wins - t.wins)
    t.record.losses = max(0, t.record.losses - t.losses)
    db.session.delete(t)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/import", methods=["POST"])
@login_required
def import_tabroom():
    url = ((request.get_json(silent=True) or {}).get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "Paste your Tabroom results link."}), 400
    result = scrape_record(url)
    result["tabroom_url"] = url
    return jsonify(result), (200 if result.get("ok") else 400)
