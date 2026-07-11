"""Native Classroom backend — Classwork: topics, posted work, attachments.

Officers post (title, optional description, links, and/or uploaded files),
grouped into topics. Everyone else views and downloads/opens attachments.
"""
import uuid

from flask import Blueprint, request, jsonify, abort, current_app, redirect
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Topic, ClassworkPost, Attachment
from ..roles import user_is_officer
from .. import storage

bp = Blueprint("classroom", __name__, url_prefix="/classroom")

_MAX_FILE = 20 * 1024 * 1024  # 20 MB


def _fmt_time(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else ""


def _att_json(a):
    return {
        "id": a.id,
        "kind": a.kind,
        "title": a.title,
        "url": a.url if a.kind == "link" else f"/classroom/attachment/{a.id}/download",
    }


def _post_json(p):
    return {
        "id": p.id,
        "title": p.title,
        "body": p.body,
        "author": (p.author.name or p.author.email) if p.author else "",
        "date": _fmt_time(p.created_at),
        "attachments": [_att_json(a) for a in p.attachments],
    }


@bp.route("/data")
@login_required
def data():
    topics = Topic.query.order_by(Topic.position, Topic.created_at).all()
    sections = [{"id": t.id, "name": t.name, "posts": [_post_json(p) for p in t.posts]} for t in topics]

    general = (
        ClassworkPost.query.filter_by(topic_id=None).order_by(ClassworkPost.created_at.desc()).all()
    )
    if general:
        sections.append({"id": None, "name": "General", "posts": [_post_json(p) for p in general]})

    return jsonify({
        "can_post": user_is_officer(),
        "storage_enabled": current_app.config.get("STORAGE_ENABLED", False),
        "topics": [{"id": t.id, "name": t.name} for t in topics],
        "sections": sections,
    })


@bp.route("/post", methods=["POST"])
@login_required
def post():
    if not user_is_officer():
        abort(403)

    title = (request.form.get("title") or "").strip()
    body = (request.form.get("body") or "").strip()
    topic_id = request.form.get("topic_id") or ""
    new_topic_name = (request.form.get("new_topic") or "").strip()

    if not title:
        return jsonify({"ok": False, "error": "Give it a title first."}), 400

    topic = None
    if new_topic_name:
        topic = Topic(name=new_topic_name[:160])
        db.session.add(topic)
        db.session.flush()
    elif topic_id.isdigit():
        topic = db.session.get(Topic, int(topic_id))

    cp = ClassworkPost(
        topic_id=topic.id if topic else None,
        author_id=current_user.id,
        title=title,
        body=body,
    )
    db.session.add(cp)
    db.session.flush()

    # Links
    link_titles = request.form.getlist("link_title")
    link_urls = request.form.getlist("link_url")
    for lt, lu in zip(link_titles, link_urls):
        lu = (lu or "").strip()
        if not lu:
            continue
        db.session.add(Attachment(
            classwork_post_id=cp.id, kind="link",
            title=(lt or lu).strip()[:255], url=lu[:600],
        ))

    # Files
    if current_app.config.get("STORAGE_ENABLED"):
        for f in request.files.getlist("files"):
            if not f or not f.filename:
                continue
            raw = f.read(_MAX_FILE + 1)
            if len(raw) > _MAX_FILE:
                return jsonify({"ok": False, "error": f"{f.filename} is over 20 MB."}), 400
            key = f"{cp.id}/{uuid.uuid4().hex}-{f.filename}"
            try:
                storage.upload(key, raw, f.content_type)
            except RuntimeError:
                return jsonify({"ok": False, "error": f"Couldn't upload {f.filename}."}), 502
            db.session.add(Attachment(
                classwork_post_id=cp.id, kind="file",
                title=f.filename[:255], storage_key=key,
                content_type=f.content_type or "", size=len(raw),
            ))

    db.session.commit()
    return jsonify({"ok": True, "post": _post_json(cp)})


@bp.route("/post/<int:post_id>/delete", methods=["POST"])
@login_required
def delete_post(post_id):
    cp = db.session.get(ClassworkPost, post_id)
    if cp is None:
        abort(404)
    if not user_is_officer() and cp.author_id != current_user.id:
        abort(403)
    for a in cp.attachments:
        if a.kind == "file" and a.storage_key:
            storage.delete(a.storage_key)
    db.session.delete(cp)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/attachment/<int:att_id>/download")
@login_required
def download(att_id):
    a = db.session.get(Attachment, att_id)
    if a is None or a.kind != "file":
        abort(404)
    url = storage.signed_url(a.storage_key)
    if not url:
        abort(502)
    return redirect(url)
