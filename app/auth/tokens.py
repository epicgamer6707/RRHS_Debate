"""Password-reset tokens.

Stateless, signed with the app SECRET_KEY (no DB column needed). Each token is:
  * time-limited (default 1 hour), and
  * single-use — it embeds a fragment of the user's current password hash, so
    once the password changes (or the token is used to change it) any older
    token stops validating.
"""
from flask import current_app
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

_SALT = "password-reset"


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=_SALT)


def _fingerprint(user):
    # Empty string for Google-only accounts that have no password yet.
    return (user.password_hash or "")[-16:]


def generate_reset_token(user):
    return _serializer().dumps({"uid": user.id, "fp": _fingerprint(user)})


def verify_reset_token(token, max_age=3600):
    """Return the User for a valid token, or None."""
    from ..models import User  # local import to avoid circulars

    try:
        data = _serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None

    user = User.query.get(data.get("uid"))
    if user is None or data.get("fp") != _fingerprint(user):
        return None
    return user
