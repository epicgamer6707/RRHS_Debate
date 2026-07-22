"""Best-effort Tabroom results reader.

Given a Tabroom results/entry URL, fetch the (public) page with the real browser
and heuristically pull a win-loss record + tournament name. Tabroom's markup
varies a lot, so this is intentionally forgiving and the UI always lets the user
correct the numbers by hand.
"""
import html as _html
import re

from .scraper import submit_fetch


def _clean(s):
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def scrape_record(url):
    if "tabroom.com" not in (url or ""):
        return {"ok": False, "error": "That doesn't look like a Tabroom link."}

    out_q = submit_fetch(url)
    if out_q is None:
        return {"ok": False, "error": "The fetcher is busy — try again in a moment."}
    try:
        kind, payload = out_q.get(timeout=45)
    except Exception:
        return {"ok": False, "error": "Couldn't reach that page."}
    if kind != "html" or not payload:
        return {"ok": False, "error": "Couldn't read that page. Enter your record manually."}

    raw = payload
    text = _clean(raw)

    # Tournament name: first <h2>/<h3>, else <title> (minus the " | Tabroom" suffix).
    name = ""
    m = re.search(r"<h[23][^>]*>(.*?)</h[23]>", raw, re.S)
    if m:
        name = _clean(m.group(1))[:120]
    if not name:
        t = re.search(r"<title[^>]*>(.*?)</title>", raw, re.S)
        if t:
            name = re.split(r"\s*[|·]\s*", _clean(t.group(1)))[0][:120]
    if name.lower() in ("tabroom.com", "tabroom"):
        name = ""

    # Prefer an explicit record like "Record 4-2" / "Prelim Record: 4-2" / "Prelims 4-2".
    wins = losses = 0
    rec = re.search(r"(?:Prelim\s+)?[Rr]ecord[:\s]+(\d+)\s*[-–]\s*(\d+)", text) \
        or re.search(r"Prelims?[:\s]+(\d+)\s*[-–]\s*(\d+)", text)
    if rec:
        wins, losses = int(rec.group(1)), int(rec.group(2))
    else:
        # Count round outcomes. Tabroom marks results as W / L or Win / Loss.
        wins = len(re.findall(r"\b(?:Win|Won)\b", text)) + len(re.findall(r"(?<![A-Za-z])W(?![A-Za-z])", text))
        losses = len(re.findall(r"\b(?:Loss|Lost)\b", text)) + len(re.findall(r"(?<![A-Za-z])L(?![A-Za-z])", text))
        # Guard against runaway counts from stray single letters.
        if wins > 40 or losses > 40:
            wins = losses = 0

    # Final placement, if the page states one ("Place: Quarterfinalist", "1st Place").
    place = ""
    pm = re.search(r"(\d+(?:st|nd|rd|th)\s+Place)", text) \
        or re.search(r"Place[:\s]+([A-Za-z0-9 ]{3,40})", text)
    if pm:
        place = pm.group(1).strip()[:60]

    ok = bool(wins or losses)
    return {
        "ok": ok,
        "error": None if ok else "Couldn't find a record on that page. Enter it manually.",
        "name": name,
        "wins": wins,
        "losses": losses,
        "place": place,
    }
