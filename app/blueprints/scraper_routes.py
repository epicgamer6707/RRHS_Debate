"""Card scraper backend.

The scraper UI is rendered inside the dashboard (main.dashboard_scraper). This
blueprint just provides the streaming scrape endpoint it talks to.
"""
import json
import queue as q_mod

from flask import Blueprint, request, jsonify, Response, stream_with_context
from flask_login import login_required

from ..scraper import submit_scrape, worker_status

bp = Blueprint("scraper", __name__)


@bp.route("/ping")
def ping():
    return jsonify(worker_status())


@bp.route("/run-automation")
@login_required
def run_automation():
    query = request.args.get("query", "").strip()
    year = request.args.get("year", "all").strip()
    event = request.args.get("event", "all").strip()

    if not query:
        def err_gen():
            yield f'data: {json.dumps({"type": "error", "error": "No query provided"})}\n\n'
        return Response(stream_with_context(err_gen()), mimetype="text/event-stream")

    out_q = submit_scrape(query, year, event)

    def generate():
        while True:
            try:
                item = out_q.get(timeout=60)
            except q_mod.Empty:
                yield f'data: {json.dumps({"type": "error", "error": "Timed out waiting for card"})}\n\n'
                return

            kind = item[0]
            if kind == "progress":
                _, current, total = item
                yield f'data: {json.dumps({"type": "progress", "current": current, "total": total})}\n\n'
            elif kind == "card":
                _, card = item
                card["type"] = "result"
                yield f'data: {json.dumps(card)}\n\n'
            elif kind == "done":
                _, count = item
                yield f'data: {json.dumps({"type": "done", "count": count})}\n\n'
                return
            elif kind == "err":
                _, msg = item
                yield f'data: {json.dumps({"type": "error", "error": msg})}\n\n'
                return

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
