"""Landing page + dashboard routes.

The dashboard is a persistent shell (sidebar) with three tool views:
Card Scraper, Sign up for Competition, and Library.
"""
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

from ..extensions import db
from ..models import SavedCard, DebateRecord, User, TabroomLink

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    # Home screen for everyone. Logged-in users see Welcome + Sign out (top right).
    return render_template("landing.html")


@bp.route("/healthz")
def healthz():
    # Pinged by an uptime bot every few minutes: keeps the free host awake AND
    # touches Postgres so Supabase's free DB doesn't pause from inactivity.
    from sqlalchemy import text
    try:
        db.session.execute(text("SELECT 1"))
        return "ok", 200
    except Exception:
        return "db-error", 500


@bp.route("/dashboard")
@login_required
def dashboard():
    record = DebateRecord.query.filter_by(user_id=current_user.id).first()
    tabroom_link = TabroomLink.query.filter_by(user_id=current_user.id, confirmed=True).first()
    leaderboard = (
        db.session.query(DebateRecord)
        .join(User, DebateRecord.user_id == User.id)
        .filter((DebateRecord.wins + DebateRecord.losses) > 0)
        .order_by(DebateRecord.wins.desc())
        .limit(10)
        .all()
    )
    return render_template(
        "dashboard/home.html", active="home", record=record,
        leaderboard=leaderboard, tabroom_link=tabroom_link,
    )


@bp.route("/dashboard/classroom")
@login_required
def dashboard_classroom():
    return render_template("dashboard/classroom.html", active="classroom")


@bp.route("/dashboard/settings")
@login_required
def dashboard_settings():
    return render_template("dashboard/settings.html", active="settings")


@bp.route("/dashboard/scraper")
@login_required
def dashboard_scraper():
    return render_template("dashboard/scraper.html", active="scraper")


@bp.route("/dashboard/signup")
@login_required
def dashboard_signup():
    # Competition sign-up now lives on the dashboard (below your stats).
    return redirect(url_for("main.dashboard"))


@bp.route("/dashboard/cutter")
@login_required
def dashboard_cutter():
    return render_template("dashboard/cutter.html", active="cutter")


@bp.route("/dashboard/citation")
@login_required
def dashboard_citation():
    return render_template("dashboard/citation.html", active="citation")


@bp.route("/dashboard/library")
@login_required
def dashboard_library():
    cards = (
        SavedCard.query
        .filter_by(user_id=current_user.id)
        .order_by(SavedCard.created_at.desc())
        .all()
    )
    return render_template("dashboard/library.html", active="library", cards=cards)
