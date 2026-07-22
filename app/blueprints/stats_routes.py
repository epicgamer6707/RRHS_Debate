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


def _apply_scrape(rec, url, result):
    """Persist a scraped Tabroom result: remember the link, and fold the
    tournament into the record without double-counting on re-refresh (dedup by
    tournament name)."""
    rec.tabroom_url = url[:600]
    name = (result.get("name") or "Tabroom results").strip()[:255]
    wins, losses = _int(result.get("wins")), _int(result.get("losses"))
    place = (result.get("place") or "").strip()[:80]

    existing = TournamentResult.query.filter_by(record_id=rec.id, name=name).first()
    if existing:
        # adjust season totals by the delta, then overwrite the row
        rec.wins = max(0, rec.wins - existing.wins + wins)
        rec.losses = max(0, rec.losses - existing.losses + losses)
        existing.wins, existing.losses = wins, losses
        if place:
            existing.place = place
    else:
        db.session.add(TournamentResult(
            record_id=rec.id, name=name, wins=wins, losses=losses, place=place,
        ))
        rec.wins += wins
        rec.losses += losses


@bp.route("/connect", methods=["POST"])
@login_required
def connect_tabroom():
    """First-time connect (and add-another): read a public Tabroom results link,
    save it, and persist the record so it stays on the dashboard."""
    url = ((request.get_json(silent=True) or {}).get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "Paste your Tabroom results link."}), 400
    result = scrape_record(url)
    if not result.get("ok"):
        return jsonify(result), 400
    rec = _record_for(current_user, create=True)
    _apply_scrape(rec, url, result)
    db.session.commit()
    return jsonify({"ok": True, "name": result.get("name"),
                    "wins": rec.wins, "losses": rec.losses})


@bp.route("/refresh", methods=["POST"])
@login_required
def refresh_tabroom():
    """Re-read the saved Tabroom link and update the record."""
    rec = _record_for(current_user)
    if rec is None or not rec.tabroom_url:
        return jsonify({"ok": False, "error": "Connect your Tabroom link first."}), 400
    result = scrape_record(rec.tabroom_url)
    if not result.get("ok"):
        return jsonify(result), 400
    _apply_scrape(rec, rec.tabroom_url, result)
    db.session.commit()
    return jsonify({"ok": True, "wins": rec.wins, "losses": rec.losses})
