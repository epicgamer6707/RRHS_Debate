"""Google Classroom reader for the Resources feed.

One officer connects (offline access, refresh token stored in ClassroomAuth).
We use that token to read the course's announcements (stream), materials
(classwork), and topics, and serve them to every logged-in member. Documents are
linked to Google Drive/Classroom, where the member downloads them with their own
Google login (so no Drive scope is needed).

Results are cached briefly so the ~1-minute auto-refresh doesn't hammer the API.
"""
import time

import requests
from flask import current_app

from .extensions import db
from .models import ClassroomAuth

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_API = "https://classroom.googleapis.com/v1"

_CACHE_TTL = 120  # seconds
_cache = {"data": None, "ts": 0}
_token_cache = {"access": None, "exp": 0}


# ── auth storage ──────────────────────────────────────────────────────────────
def save_auth(refresh_token, email):
    ClassroomAuth.query.delete()
    db.session.add(ClassroomAuth(refresh_token=refresh_token, email=email or ""))
    db.session.commit()
    _cache["data"] = None
    _token_cache["access"] = None


def clear_auth():
    ClassroomAuth.query.delete()
    db.session.commit()
    _cache["data"] = None
    _token_cache["access"] = None


def _auth_row():
    return ClassroomAuth.query.first()


def is_connected():
    return _auth_row() is not None


def connected_email():
    row = _auth_row()
    return row.email if row else ""


# ── access token ──────────────────────────────────────────────────────────────
def _access_token():
    now = time.time()
    if _token_cache["access"] and _token_cache["exp"] > now + 30:
        return _token_cache["access"]
    row = _auth_row()
    if not row:
        return None
    resp = requests.post(_TOKEN_URL, data={
        "client_id": current_app.config["GOOGLE_CLIENT_ID"],
        "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
        "refresh_token": row.refresh_token,
        "grant_type": "refresh_token",
    }, timeout=15)
    if resp.status_code >= 400:
        current_app.logger.error("[classroom] token refresh failed %s: %s", resp.status_code, resp.text)
        return None
    tok = resp.json()
    _token_cache["access"] = tok.get("access_token")
    _token_cache["exp"] = now + int(tok.get("expires_in", 3600))
    return _token_cache["access"]


# ── API helpers ───────────────────────────────────────────────────────────────
def _get(path, token, params=None, key=None):
    """GET a paginated Classroom list endpoint; return the accumulated items."""
    params = dict(params or {})
    params["pageSize"] = 100
    items = []
    headers = {"Authorization": f"Bearer {token}"}
    while True:
        r = requests.get(_API + path, headers=headers, params=params, timeout=20)
        if r.status_code >= 400:
            current_app.logger.error("[classroom] %s -> %s: %s", path, r.status_code, r.text[:300])
            break
        data = r.json()
        if key:
            items.extend(data.get(key, []))
        token_next = data.get("nextPageToken")
        if not token_next:
            break
        params["pageToken"] = token_next
    return items


def _attachments(materials):
    out = []
    for m in materials or []:
        if "driveFile" in m:
            f = m["driveFile"].get("driveFile", {})
            out.append({"title": f.get("title", "File"), "link": f.get("alternateLink", ""), "type": "file"})
        elif "link" in m:
            out.append({"title": m["link"].get("title") or m["link"].get("url", "Link"),
                        "link": m["link"].get("url", ""), "type": "link"})
        elif "youtubeVideo" in m:
            y = m["youtubeVideo"]
            out.append({"title": y.get("title", "Video"), "link": y.get("alternateLink", ""), "type": "video"})
        elif "form" in m:
            fo = m["form"]
            out.append({"title": fo.get("title", "Form"), "link": fo.get("formUrl", ""), "type": "form"})
    return out


def _first_line(text, fallback):
    t = (text or "").strip()
    if not t:
        return fallback
    return t.split("\n", 1)[0][:120]


def _build_feed():
    token = _access_token()
    if not token:
        return {"connected": True, "error": "reconnect", "stream": [], "sections": []}

    course_id = current_app.config["CLASSROOM_COURSE_ID"]
    base = f"/courses/{course_id}"

    topics = _get(f"{base}/topics", token, key="topic")
    topic_name = {t["topicId"]: t.get("name", "Untitled") for t in topics}
    topic_order = [t["topicId"] for t in topics]

    announcements = _get(f"{base}/announcements", token,
                         params={"announcementStates": "PUBLISHED", "orderBy": "updateTime desc"},
                         key="announcements")
    materials = _get(f"{base}/courseWorkMaterials", token,
                     params={"courseWorkMaterialStates": "PUBLISHED"},
                     key="courseWorkMaterial")

    stream = [{
        "id": a.get("id"),
        "title": _first_line(a.get("text"), "Announcement"),
        "text": a.get("text", ""),
        "date": a.get("updateTime") or a.get("creationTime", ""),
        "link": a.get("alternateLink", ""),
        "attachments": _attachments(a.get("materials")),
    } for a in announcements]

    # group materials by topic
    by_topic = {}
    for m in materials:
        tid = m.get("topicId", "__none__")
        by_topic.setdefault(tid, []).append({
            "id": m.get("id"),
            "title": m.get("title", "Material"),
            "text": m.get("description", ""),
            "date": m.get("updateTime") or m.get("creationTime", ""),
            "link": m.get("alternateLink", ""),
            "attachments": _attachments(m.get("materials")),
        })

    sections = []
    for tid in topic_order:
        if tid in by_topic:
            sections.append({"topic": topic_name.get(tid, "Topic"), "items": by_topic[tid]})
    if "__none__" in by_topic:
        sections.append({"topic": "General", "items": by_topic["__none__"]})

    return {
        "connected": True,
        "error": None,
        "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "stream": stream,
        "sections": sections,
    }


def get_feed(force=False):
    if not is_connected():
        return {"connected": False, "stream": [], "sections": []}
    now = time.time()
    if not force and _cache["data"] and (now - _cache["ts"]) < _CACHE_TTL:
        return _cache["data"]
    try:
        data = _build_feed()
    except requests.RequestException as e:
        current_app.logger.error("[classroom] fetch failed: %s", e)
        return _cache["data"] or {"connected": True, "error": "fetch", "stream": [], "sections": []}
    _cache["data"] = data
    _cache["ts"] = now
    return data
