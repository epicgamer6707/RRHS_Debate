"""Signup / login / logout routes (email + password).

Google sign-in (Part C) and forgot-password (Part B) will be added to this same
blueprint later.
"""
from urllib.parse import urlparse

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from ..extensions import db
from ..models import User
from .forms import SignupForm, LoginForm

bp = Blueprint("auth", __name__)


def _safe_next(target):
    """Only allow same-site relative redirects (avoid open-redirect attacks)."""
    if not target:
        return None
    parsed = urlparse(target)
    if parsed.scheme == "" and parsed.netloc == "" and target.startswith("/"):
        return target
    return None


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = SignupForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists. Try signing in.", "error")
        else:
            user = User(email=email, name=form.name.data.strip())
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Welcome to RRHS Debate!", "success")
            return redirect(url_for("main.dashboard"))

    return render_template("auth/signup.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(form.password.data):
            flash("Incorrect email or password.", "error")
        else:
            login_user(user, remember=form.remember.data)
            nxt = _safe_next(request.args.get("next"))
            return redirect(nxt or url_for("main.dashboard"))

    return render_template("auth/login.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You've been signed out.", "info")
    return redirect(url_for("auth.login"))
