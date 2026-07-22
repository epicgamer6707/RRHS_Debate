"""Server-side AI via Groq (free, no credit card, OpenAI-compatible, fast).

Runs on the server so it works on every device, no big in-browser download.
Set GROQ_API_KEY (free from console.groq.com) to enable.
"""
import json

import requests
from flask import current_app

_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


def ai_enabled():
    return bool(current_app.config.get("GROQ_API_KEY"))


def _chat(messages, max_tokens=1000, temperature=0.4, json_mode=False):
    """Return (text, error). One is always None."""
    key = current_app.config.get("GROQ_API_KEY")
    if not key:
        return None, "AI isn't set up yet — an officer needs to add a free Groq API key."

    payload = {
        "model": current_app.config.get("AI_MODEL", "llama-3.3-70b-versatile"),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    try:
        r = requests.post(
            _ENDPOINT,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=45,
        )
    except requests.RequestException:
        return None, "Couldn't reach the AI service. Try again."

    if r.status_code == 429:
        return None, "AI hit today's free limit or is busy. Try again shortly."
    if r.status_code >= 400:
        current_app.logger.error("[ai] %s: %s", r.status_code, r.text[:300])
        return None, f"AI error ({r.status_code})."
    try:
        return r.json()["choices"][0]["message"]["content"].strip(), None
    except (KeyError, IndexError, ValueError):
        return None, "AI returned an unexpected response."


def ask(prompt, system=None, **kw):
    messages = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
    return _chat(messages, **kw)


def chat(history, system=None, **kw):
    """history: list of {role, content} from the browser."""
    messages = ([{"role": "system", "content": system}] if system else []) + list(history)
    return _chat(messages, **kw)


def _extract_json(raw):
    """Pull a JSON object out of a model reply, tolerant of fences/prose."""
    if not raw:
        return None
    raw = raw.strip()
    # Strip ```json ... ``` fences if present.
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1] if raw.count("```") >= 2 else raw
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]
    try:
        return json.loads(raw)
    except ValueError:
        pass
    import re
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except ValueError:
        return None


def analyze_segments(text, idea):
    """Structured breakdown tied to the student's idea, plus a summary tagline.
    Returns ({"tagline": str, "segments": [...]}, error)."""
    idea = idea or ""
    system = (
        "You are an expert policy/LD debate coach. You read a piece of evidence (a 'card') "
        "and, keeping the student's idea in mind, (1) write a punchy one-line tagline for the "
        "card, and (2) break it into the parts that matter, labeling each part's role. "
        "Roles: interp, warrant, link, impact, uniqueness, context. Only quote text that "
        "appears verbatim in the evidence. Always respond with a single valid JSON object."
    )
    prompt = (
        f"The student's idea/argument: \"{idea or 'general analysis'}\"\n\n"
        f"Evidence:\n\"\"\"\n{text[:6000]}\n\"\"\"\n\n"
        "Return JSON exactly like: {\"tagline\": \"<punchy one-line tag for this card, "
        "framed toward the student's idea>\", \"segments\": [{\"quote\": \"<exact sentence "
        "copied from the evidence>\", \"role\": \"warrant|interp|link|impact|uniqueness|context\", "
        "\"note\": \"<one short sentence on how this part helps THEIR idea>\"}]}. "
        "Pick the 3-6 segments most useful for their idea. Every quote MUST be copied "
        "exactly (character-for-character) from the evidence."
    )
    raw, err = _chat(
        [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        max_tokens=1300, temperature=0.2, json_mode=True,
    )
    if err:
        return None, err
    data = _extract_json(raw)
    if not isinstance(data, dict):
        return None, "Couldn't parse the analysis. Try again."
    segs = [s for s in data.get("segments", []) if isinstance(s, dict) and s.get("quote")]
    return {"tagline": (data.get("tagline") or "").strip(), "segments": segs}, None
