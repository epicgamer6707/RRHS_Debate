"""Transactional email via the Resend HTTP API.

If no RESEND_API_KEY is configured (e.g. local dev), we log the message to the
console instead of sending, so the reset flow is still testable.
"""
import requests
from flask import current_app

_RESEND_ENDPOINT = "https://api.resend.com/emails"


def send_email(to, subject, html):
    """Return True if handed off to Resend (or logged in dev), False on error."""
    if not current_app.config.get("EMAIL_ENABLED"):
        current_app.logger.warning(
            "[email] EMAIL not configured — would send to %s: %s\n%s",
            to, subject, html,
        )
        return True  # treat as "sent" so the UX is identical in dev

    try:
        resp = requests.post(
            _RESEND_ENDPOINT,
            headers={
                "Authorization": f"Bearer {current_app.config['RESEND_API_KEY']}",
                "Content-Type": "application/json",
            },
            json={
                "from": current_app.config["MAIL_FROM"],
                "to": [to],
                "subject": subject,
                "html": html,
            },
            timeout=10,
        )
    except requests.RequestException as e:
        current_app.logger.error("[email] request failed: %s", e)
        return False

    if resp.status_code >= 400:
        current_app.logger.error("[email] Resend error %s: %s", resp.status_code, resp.text)
        return False
    return True


def send_password_reset(user, reset_url):
    subject = "Reset your RRHS Debate password"
    html = f"""
    <div style="font-family:-apple-system,Segoe UI,Arial,sans-serif;max-width:480px;margin:0 auto;">
      <h2 style="color:#25274D;">Reset your password</h2>
      <p style="color:#464866;font-size:15px;line-height:1.6;">
        Hi {user.name or "there"}, we got a request to reset your RRHS Debate password.
        Click the button below to choose a new one. This link expires in 1 hour.
      </p>
      <p style="margin:26px 0;">
        <a href="{reset_url}"
           style="background:#2E9CCA;color:#fff;text-decoration:none;padding:12px 22px;
                  border-radius:9px;font-weight:700;display:inline-block;">
          Reset password
        </a>
      </p>
      <p style="color:#9a958f;font-size:13px;line-height:1.6;">
        If you didn't request this, you can safely ignore this email.<br>
        Or paste this link into your browser:<br>
        <a href="{reset_url}" style="color:#29648A;">{reset_url}</a>
      </p>
    </div>
    """
    return send_email(user.email, subject, html)
