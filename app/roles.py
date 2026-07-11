"""Officer permission check.

An officer may post to the Classroom. Officers are listed in OFFICER_EMAILS
(comma-separated, set in Railway). If that list is empty, everyone can post so
the feature works out of the box until you lock it down.
"""
from flask import current_app
from flask_login import current_user


def user_is_officer(user=None):
    u = user if user is not None else current_user
    if not getattr(u, "is_authenticated", False):
        return False
    emails = current_app.config.get("OFFICER_EMAILS") or []
    if not emails:
        return True  # no officer list configured -> everyone can post
    return (u.email or "").lower() in emails
