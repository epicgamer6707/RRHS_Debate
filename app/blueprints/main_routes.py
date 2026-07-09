"""Landing page + dashboard routes."""
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    # Signed-in users skip the marketing page and go straight to their dashboard.
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("landing.html")


@bp.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=current_user)
