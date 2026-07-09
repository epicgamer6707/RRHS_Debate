"""Signup / login / logout routes (email + password).

Google sign-in (Part C) and forgot-password (Part B) will be added to this same
blueprint later.
"""
from urllib.parse import urlparse

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user

from ..extensions import db, oauth
from ..models import User
from ..email import send_password_reset
from .forms import SignupForm, LoginForm, ForgotForm, ResetPasswordForm
from .tokens import generate_reset_token, verify_reset_token

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


# ── Forgot / reset password ───────────────────────────────────────────────────
@bp.route("/forgot", methods=["GET", "POST"])
def forgot():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = ForgotForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            token = generate_reset_token(user)
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            send_password_reset(user, reset_url)
        # Always show the same message — don't reveal whether an email exists.
        flash("If that email has an account, we've sent a reset link.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot.html", form=form)


@bp.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    user = verify_reset_token(token)
    if user is None:
        flash("That reset link is invalid or has expired. Request a new one.", "error")
        return redirect(url_for("auth.forgot"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()  # changes the hash, invalidating this (now-used) token
        flash("Your password has been reset. Please sign in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset.html", form=form)


# ── Google OAuth ──────────────────────────────────────────────────────────────
@bp.route("/login/google")
def google_login():
    if not current_app.config.get("GOOGLE_ENABLED"):
        flash("Google sign-in isn't configured yet.", "error")
        return redirect(url_for("auth.login"))
    redirect_uri = url_for("auth.google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@bp.route("/login/google/callback")
def google_callback():
    if not current_app.config.get("GOOGLE_ENABLED"):
        flash("Google sign-in isn't configured yet.", "error")
        return redirect(url_for("auth.login"))

    try:
        token = oauth.google.authorize_access_token()
    except Exception:
        flash("Google sign-in failed or was cancelled.", "error")
        return redirect(url_for("auth.login"))

    info = token.get("userinfo") or {}
    sub = info.get("sub")
    email = (info.get("email") or "").strip().lower()
    if not sub or not email:
        flash("Google didn't return your email. Please try another method.", "error")
        return redirect(url_for("auth.login"))

    # Match by Google id first, then by email (link an existing password account).
    user = User.query.filter_by(google_id=sub).first()
    if user is None:
        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(email=email, name=info.get("name", ""), google_id=sub)
            db.session.add(user)
        else:
            user.google_id = sub
        db.session.commit()

    login_user(user)
    return redirect(url_for("main.dashboard"))
