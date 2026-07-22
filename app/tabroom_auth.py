"""Tabroom account sign-in — used ONCE to log in, then the password is discarded.

Tabroom's login form hashes the password client-side with SHA-512 crypt ($6$)
against a per-page salt. We reproduce that with passlib and post the hash, so we
authenticate the same way the browser does. We keep only the resulting login
*session cookies* (to keep reading the user's results); the plaintext password is
never stored and never leaves this function.
"""
import json
import re

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


def fetch_results(cookies_dict):
    """Read the signed-in user's results. Returns (result, error) where result is
    {"wins", "losses", "authed"}. If the session is dead, authed=False."""
    s = _session_from(cookies_dict)
    try:
        r = s.get(_STUDENT, timeout=30, allow_redirects=True)
    except requests.RequestException:
        return None, "Couldn't reach Tabroom."
    if "login" in r.url:  # bounced to login → session expired
        return {"authed": False}, None

    text = _text(r.text)

    # Sum explicit per-tournament records like "4-2" / "Prelims 4-2"; guard sanity.
    pairs = re.findall(r"(?:Prelims?|Record)[:\s]+(\d+)\s*[-–]\s*(\d+)", text)
    wins = losses = 0
    if pairs:
        for w, l in pairs:
            wins += int(w); losses += int(l)
    else:
        wins = len(re.findall(r"\b(?:Win|Won)\b", text))
        losses = len(re.findall(r"\b(?:Loss|Lost)\b", text))
    if wins > 200 or losses > 200:
        wins = losses = 0
    return {"authed": True, "wins": wins, "losses": losses}, None


def cookies_to_json(cookies_dict):
    return json.dumps(cookies_dict or {})


def cookies_from_json(s):
    try:
        return json.loads(s or "{}")
    except ValueError:
        return {}
