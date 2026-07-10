"""Tabroom.com tournament scraper.

Given any Tabroom tournament URL (or a bare tourn_id), fetch the public
tournament index page and pull the tournament name, dates, and location.

Note: Tabroom now login-gates its events/fields pages, so we don't scrape the
per-tournament event list — the UI offers a standard event dropdown instead.
"""
import html as _html
import re

import requests

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
)
_INDEX = "https://www.tabroom.com/index/tourn/index.mhtml?tourn_id={}"


def _clean(s):
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def extract_tourn_id(url_or_id):
    """Pull a tourn_id from a Tabroom URL, or accept a bare numeric id."""
    s = (url_or_id or "").strip()
    if s.isdigit():
        return s
    m = re.search(r"tourn_id=(\d+)", s)
    return m.group(1) if m else None


def scrape_tournament(url_or_id):
    """Return {ok, name, date, location, tourn_id, url} or {ok: False, error}."""
    tourn_id = extract_tourn_id(url_or_id)
    if not tourn_id:
        return {"ok": False, "error": "That doesn't look like a Tabroom tournament link."}

    index_url = _INDEX.format(tourn_id)
    try:
        resp = requests.get(index_url, headers={"User-Agent": _UA}, timeout=20)
    except requests.RequestException:
        return {"ok": False, "error": "Couldn't reach Tabroom. Try again in a moment."}

    if resp.status_code != 200:
        return {"ok": False, "error": f"Tabroom returned status {resp.status_code}."}

    raw = resp.text

    name_m = re.search(r"<h2[^>]*>(.*?)</h2>", raw, re.S)
    name = _clean(name_m.group(1)) if name_m else ""
    if not name:
        return {"ok": False, "error": "Couldn't find a tournament at that link."}

    # "2026 — Ann Arbor, MI/US" → year + location
    h5_m = re.search(r"<h5[^>]*>(.*?)</h5>", raw, re.S)
    h5 = _clean(h5_m.group(1)) if h5_m else ""
    location = ""
    if "—" in h5:
        location = h5.split("—", 1)[1].strip()
    elif h5:
        location = h5

    # "... Tournament Dates Jul 4 to Jul 7 2026 Registration ..."
    text = _clean(raw)
    date_m = re.search(r"Tournament Dates\s+(.+?\d{4})", text)
    date = date_m.group(1).strip() if date_m else ""

    return {
        "ok": True,
        "name": name,
        "date": date,
        "location": location,
        "tourn_id": tourn_id,
        "url": index_url,
    }
