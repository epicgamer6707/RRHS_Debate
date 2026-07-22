"""AI endpoints (server-side, via Groq): Analyzer segments + the Bot chat."""
from flask import Blueprint, request, jsonify
from flask_login import login_required

from ..ai import analyze_segments, chat, ask, ai_enabled

bp = Blueprint("ai", __name__, url_prefix="/ai")

_BOT_SYSTEM = (
    "You are a sharp, friendly policy/LD debate assistant helping a high schooler. "
    "You are given a piece of evidence (a 'card'). Answer questions about it. When asked "
    "for a warrant, link, or specific part, quote the EXACT sentence(s) from the card. When "
    "asked for a tagline, write one short, punchy sentence. Be concise, no markdown symbols."
)


@bp.route("/status")
@login_required
def status():
    return jsonify({"enabled": ai_enabled()})


@bp.route("/analyze", methods=["POST"])
@login_required
def analyze():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    idea = (data.get("idea") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "Nothing to analyze."}), 400
    result, err = analyze_segments(text, idea)
    if err:
        return jsonify({"ok": False, "error": err}), 400
    return jsonify({"ok": True, "tagline": result["tagline"], "segments": result["segments"]})


@bp.route("/keywords", methods=["POST"])
@login_required
def keywords():
    req = ((request.get_json(silent=True) or {}).get("request") or "").strip()
    if not req:
        return jsonify({"ok": False, "error": "Type what you're looking for."}), 400
    text, err = ask(
        "You convert a debater's plain-English request into a short keyword query for a "
        "card database (haku.cards) that matches on tags, authors and topics.\n"
        "Rules:\n"
        "- Keep the ACTUAL topic words: proper nouns, theorists, authors and concepts "
        "(e.g. Deleuze, Lacan, psychoanalysis, protectionism, deterrence) MUST survive.\n"
        "- Expand debate shorthand into searchable words: AT/A2 -> answers to, K -> kritik, "
        "CP -> counterplan, DA -> disadvantage, TOP -> stays 'TOP' if it's a proper name.\n"
        "- Drop filler like 'give me', 'find', 'a', 'that breaks'.\n"
        "- Output 2-6 keywords separated by spaces. No quotes, no punctuation, no explanation.\n\n"
        f"Request: {req}\nKeywords:",
        system="You are a precise policy debate research assistant. Output only keywords.",
        max_tokens=40, temperature=0.1,
    )
    if err:
        return jsonify({"ok": False, "error": err}), 400
    kw = (text or "").replace('"', "").replace("Keywords:", "").split("\n")[0].strip()[:90]
    return jsonify({"ok": True, "keywords": kw or req[:90]})


@bp.route("/chat", methods=["POST"])
@login_required
def bot_chat():
    data = request.get_json(silent=True) or {}
    card = (data.get("card") or "").strip()
    history = data.get("messages") or []
    if not history:
        return jsonify({"ok": False, "error": "Ask something first."}), 400
    # Keep only role/content, cap history so we don't blow the token budget.
    clean = [{"role": m.get("role"), "content": str(m.get("content", ""))[:2000]}
             for m in history[-10:] if m.get("role") in ("user", "assistant")]
    system = _BOT_SYSTEM
    if card:
        system += f"\n\nThe card:\n\"\"\"\n{card[:6000]}\n\"\"\""
    reply, err = chat(clean, system=system, max_tokens=800)
    if err:
        return jsonify({"ok": False, "error": err}), 400
    return jsonify({"ok": True, "reply": reply})
