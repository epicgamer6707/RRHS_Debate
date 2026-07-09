"""Dashboard route.

Temporary Part-A shell: just proves login works by greeting the user. Phase 3
fills this in with the real sidebar (Card Scraper / Sign up / Library).
"""
from flask import Blueprint, render_template
from flask_login import login_required, current_user

bp = Blueprint("main", __name__)


@bp.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=current_user)
