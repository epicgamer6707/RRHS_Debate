"""Landing page + dashboard routes.

The dashboard is a persistent shell (sidebar) with three tool views:
Card Scraper, Sign up for Competition, and Library.
"""
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

from ..models import SavedCard

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    # Home screen for everyone. Logged-in users see Welcome + Sign out (top right).
    return render_template("landing.html")


@bp.route("/dashboard")
@login_required
def dashboard():
    # Default landing tool inside the dashboard.
    return redirect(url_for("main.dashboard_scraper"))


@bp.route("/dashboard/resources")
@login_required
def dashboard_resources():
    from ..google_classroom import is_connected, connected_email
    return render_template(
        "dashboard/resources.html",
        active="resources",
        connected=is_connected(),
        connected_email=connected_email(),
    )


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
    return render_template("dashboard/signup.html", active="signup")


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
