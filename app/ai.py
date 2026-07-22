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


def analyze_segments(text, idea):
    """Ask for a structured breakdown: which sentences serve which role, and how
    each helps the student's idea. Returns (segments_list, error)."""
    system = (
        "You are an expert policy/LD debate coach. You break a piece of evidence into "
        "the parts that matter and label each part's role. Roles: interp, warrant, link, "
        "impact, uniqueness, context. Only quote text that appears verbatim in the "
        "evidence. Respond ONLY as JSON."
    )
    prompt = (
        f"The student's idea/argument: \"{idea or 'general analysis'}\"\n\n"
        f"Evidence:\n\"\"\"\n{text[:6000]}\n\"\"\"\n\n"
        "Return JSON: {\"segments\": [{\"quote\": \"<exact sentence from the evidence>\", "
        "\"role\": \"warrant|interp|link|impact|uniqueness|context\", "
        "\"note\": \"<one short sentence on how this part helps their idea>\"}]}. "
        "Pick the 3-6 most important segments. Each quote MUST be copied exactly from the evidence."
    )
    raw, err = _chat(
        [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        max_tokens=1200, temperature=0.2,
    )
    if err:
        return None, err
    # Parse robustly across models: pull the first {...} block out of the reply.
    import re
    m = re.search(r"\{.*\}", raw or "", re.DOTALL)
    try:
        data = json.loads(m.group(0) if m else raw)
        segs = data.get("segments", [])
        return [s for s in segs if s.get("quote")], None
    except (ValueError, AttributeError):
        return None, "Couldn't parse the analysis. Try again."
