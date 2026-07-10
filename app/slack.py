"""Slack notifications via an incoming webhook.

When SLACK_WEBHOOK_URL isn't configured (e.g. before the webhook is set up) we
log instead of sending, and report delivered=False so the UI can be honest.
"""
import requests
from flask import current_app


def send_signup_notification(user, signup):
    """Post a competition-signup request to the officers' channel.

    `signup` is a dict with name / date / location / event / url.
    Returns True if actually delivered to Slack, False otherwise.
    """
    who = user.name or user.email
    name = signup.get("name") or "—"
    date = signup.get("date") or "—"
    location = signup.get("location") or "—"
    event = signup.get("event") or "—"
    url = signup.get("url") or ""

    fallback = f"{who} wants to sign up for {name} ({event})"

    if not current_app.config.get("SLACK_ENABLED"):
        current_app.logger.warning("[slack] not configured — would send: %s", fallback)
        return False

    fields = [
        {"type": "mrkdwn", "text": f"*Tournament:*\n{name}"},
        {"type": "mrkdwn", "text": f"*Event:*\n{event}"},
        {"type": "mrkdwn", "text": f"*Dates:*\n{date}"},
        {"type": "mrkdwn", "text": f"*Location:*\n{location}"},
        {"type": "mrkdwn", "text": f"*Requested by:*\n{who}"},
        {"type": "mrkdwn", "text": f"*Email:*\n{user.email}"},
    ]
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn",
            "text": f":wave: *{who}* wants to sign up for a tournament."}},
        {"type": "section", "fields": fields},
    ]
    if url:
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": f"<{url}|View on Tabroom>"}})

    try:
        resp = requests.post(
            current_app.config["SLACK_WEBHOOK_URL"],
            json={"text": fallback, "blocks": blocks},
            timeout=10,
        )
    except requests.RequestException as e:
        current_app.logger.error("[slack] request failed: %s", e)
        return False

    if resp.status_code >= 400:
        current_app.logger.error("[slack] error %s: %s", resp.status_code, resp.text)
        return False
    return True
