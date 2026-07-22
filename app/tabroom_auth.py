"""Tabroom account sign-in — used ONCE to log in, then the password is discarded.

Tabroom's login form hashes the password client-side with SHA-512 crypt ($6$)
against a per-page salt. We reproduce that with passlib and post the hash, so we
authenticate the same way the browser does. We keep only the resulting login
*session cookies* (to keep reading the user's results); the plaintext password is
never stored and never leaves this function.
"""
import json
import re
from urllib.parse import urljoin

import requests
from passlib.hash import sha512_crypt

_BASE = "https://www.tabroom.com"
_LOGIN = _BASE + "/user/login/login.mhtml"
_LOGIN_SAVE = _BASE + "/user/login/login_save.mhtml"
_STUDENT = _BASE + "/user/student/index.mhtml"
_HOME = _BASE + "/user/home.mhtml"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
}


def _text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def login(email, password):
    """Sign in to Tabroom. Returns (session_cookies_dict, identity, error).

    identity = {"name": str, "school": str}. On failure the first two are None.
    The `password` argument is used only here and is not retained.
    """
    if not email or not password:
        return None, None, "Enter your Tabroom email and password."

    s = requests.Session()
    s.headers.update(_HEADERS)
    try:
        lp = s.get(_LOGIN, timeout=25).text
    except requests.RequestException:
        return None, None, "Couldn't reach Tabroom. Try again."

    m = re.search(r'name\s*=\s*"salt"\s*value\s*=\s*"([^"]+)"', lp)
    if not m:
        return None, None, "Tabroom's login page changed — reconnect isn't available right now."
    salt = m.group(1)
    # Mirror Tabroom's client-side hashing: crypt(3) SHA-512, 5000 rounds.
    sha = sha512_crypt.using(salt=salt, rounds=5000).hash(password)

    try:
        r = s.post(
            _LOGIN_SAVE, allow_redirects=False, timeout=25,
            data={"username": email, "password": password, "salt": salt, "sha": sha},
        )
    except requests.RequestException:
        return None, None, "Couldn't reach Tabroom. Try again."
    finally:
        password = None  # drop the plaintext immediately

    loc = r.headers.get("location", "") or ""
    if "err=" in loc or "login.mhtml" in loc:
        return None, None, "Your Tabroom email or password wasn't correct."
    if not s.cookies:
        return None, None, "Tabroom didn't accept that sign-in. Double-check your credentials."

    identity = _fetch_identity(s)
    return requests.utils.dict_from_cookiejar(s.cookies), identity, None


def _session_from(cookies_dict):
    s = requests.Session()
    s.headers.update(_HEADERS)
    if cookies_dict:
        s.cookies.update(cookies_dict)
    return s


def _fetch_identity(s):
    """Best-effort display name + school for the 'is this you?' step."""
    name, school = "", ""
    try:
        html = s.get(_HOME, timeout=25).text
    except requests.RequestException:
        return {"name": "", "school": ""}
    # Logged-in Tabroom shows the person's name linking to their profile.
    m = re.search(r'profile\.mhtml"[^>]*>(.*?)</a>', html, re.S)
    if m:
        name = _text(m.group(1))[:120]
    if not name:
        t = re.search(r"<title[^>]*>(.*?)</title>", html, re.S)
        if t:
            name = re.split(r"\s*[|·]\s*", _text(t.group(1)))[0][:120]
    sm = re.search(r"([A-Z][\w.&' -]+(?:High School|HS|Academy|University|College))", _text(html))
    if sm:
        school = sm.group(1).strip()[:120]
    if name.lower() in ("tabroom.com", "tabroom", "home"):
        name = ""
    return {"name": name, "school": school}


_ROUND_START = re.compile(
    r"^(Round\s*\d+|R\d+|Octo|Double|Triple|Quarter|Semi|Final|Bergen|"
    r"Round of|Elim|Prelim|Partial|Playoff|Runoff)", re.I)
_LETTER = re.compile(r"(?<![A-Za-z])([WL])(?![A-Za-z])")
_DATE = re.compile(r"\d{1,2}\s+[A-Za-z]{3,9}\.?\s+\d{4}")
_DIVISION = re.compile(
    r"Lincoln-Douglas|Policy|Public Forum|Congress|Parli|World|Extemp|"
    r"Oratory|Interp|Debate|Speech|\bLD\b|\bPF\b|\bCX\b|\bBQ\b", re.I)


def _rows(html):
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)
        yield tr, [_text(c) for c in cells]


def _parse_index(html):
    """Tournaments from the 'History at …' table: name, date, division, detail link."""
    i = html.find("History at")
    region = html[i:] if i != -1 else html
    out = []
    for tr, cells in _rows(region):
        if not cells:
            continue
        date = next((c for c in cells if _DATE.match(c)), "")
        if not date:
            continue  # header or non-tournament row
        name = cells[0][:255]
        division = next((c for c in cells if _DIVISION.search(c)), "")[:120]
        m = re.search(r'href\s*=\s*"([^"]+)"', tr)
        out.append({"name": name, "date": date[:80], "division": division,
                    "link": m.group(1) if m else "", "wins": 0, "losses": 0})
    return out


def _count_wl(html):
    """Count round wins/losses on an entry-record page. Groups panel ballots per
    round (a round row followed by extra judge rows) and takes the majority."""
    rounds = []
    for _tr, cells in _rows(html):
        if not cells:
            continue
        first = cells[0]
        letters = _LETTER.findall(" ".join(cells[1:]))  # skip the round-label cell
        if _ROUND_START.match(first):
            rounds.append(list(letters))
        elif rounds and letters and not first:
            rounds[-1].extend(letters)  # continuation row (more judges on a panel)
    wins = losses = 0
    for rl in rounds:
        w, l = rl.count("W"), rl.count("L")
        if w > l:
            wins += 1
        elif l > w:
            losses += 1
    return wins, losses


def fetch_results(cookies_dict):
    """Read the signed-in user's results. Returns (result, error) where result is
    {"authed", "wins", "losses", "tournaments": [...]}. authed=False if session died."""
    s = _session_from(cookies_dict)
    try:
        r = s.get(_STUDENT, timeout=30, allow_redirects=True)
    except requests.RequestException:
        return None, "Couldn't reach Tabroom."
    if "login" in r.url:  # bounced to login → session expired
        return {"authed": False}, None

    tournaments = _parse_index(r.text)
    for t in tournaments[:15]:
        if not t["link"]:
            continue
        try:
            detail = s.get(urljoin(_BASE, t["link"]), timeout=25).text
        except requests.RequestException:
            continue
        t["wins"], t["losses"] = _count_wl(detail)

    wins = sum(t["wins"] for t in tournaments)
    losses = sum(t["losses"] for t in tournaments)
    return {"authed": True, "wins": wins, "losses": losses, "tournaments": tournaments}, None


def cookies_to_json(cookies_dict):
    return json.dumps(cookies_dict or {})


def cookies_from_json(s):
    try:
        return json.loads(s or "{}")
    except ValueError:
        return {}
