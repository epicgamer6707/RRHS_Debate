"""Build the Logs page changelog from the GitHub commit history.

Commits are grouped into "updates": a burst of commits with no gap longer than
GAP_DAYS becomes one update (the user works for a stretch, waits a few days, works
again). Each update lists a one-line summary per commit. Cached for an hour so we
don't hammer the unauthenticated GitHub API (60 req/hr).
"""
import time
from datetime import datetime

import requests

_REPO = "AryanSharma238/RRHS-Debate-Website"
_API = f"https://api.github.com/repos/{_REPO}/commits?per_page=100"
_GAP_DAYS = 1.0          # a gap longer than this starts a new update
_CACHE_TTL = 3600        # seconds
_cache = {"at": 0.0, "updates": None}

_HIDE = ("merge branch", "merge pull request", "co-authored-by")


def _clean_summary(message):
    """First line of a commit message, tidied."""
    line = (message or "").strip().split("\n", 1)[0].strip()
    return line


def _fetch_commits():
    r = requests.get(_API, timeout=15, headers={"Accept": "application/vnd.github+json"})
    r.raise_for_status()
    out = []
    for c in r.json():
        commit = c.get("commit", {})
        msg = commit.get("message", "")
        if not msg or msg.lower().startswith(_HIDE):
            continue
        when = (commit.get("author") or {}).get("date") or (commit.get("committer") or {}).get("date")
        if not when:
            continue
        dt = datetime.strptime(when, "%Y-%m-%dT%H:%M:%SZ")
        out.append({"summary": _clean_summary(msg), "dt": dt})
    return out


def _group(commits):
    """Group commits (newest first) into updates by date gaps."""
    updates = []
    cur = None
    for c in commits:
        if cur is None:
            cur = {"lines": [c["summary"]], "start": c["dt"], "end": c["dt"]}
            continue
        gap = (cur["end"] - c["dt"]).total_seconds() / 86400.0
        if gap > _GAP_DAYS:
            updates.append(cur)
            cur = {"lines": [c["summary"]], "start": c["dt"], "end": c["dt"]}
        else:
            cur["lines"].append(c["summary"])
            cur["end"] = c["dt"]
    if cur:
        updates.append(cur)

    # format date labels
    for u in updates:
        s, e = u["start"], u["end"]
        if s.date() == e.date():
            u["date_label"] = s.strftime("%b %-d, %Y")
        elif s.year == e.year:
            u["date_label"] = f"{e.strftime('%b %-d')} – {s.strftime('%b %-d, %Y')}"
        else:
            u["date_label"] = f"{e.strftime('%b %-d, %Y')} – {s.strftime('%b %-d, %Y')}"
    return updates


def get_updates():
    """Return the changelog updates, cached. On failure returns (updates, error)."""
    now = time.time()
    if _cache["updates"] is not None and now - _cache["at"] < _CACHE_TTL:
        return _cache["updates"], None
    try:
        updates = _group(_fetch_commits())
    except (requests.RequestException, ValueError, KeyError) as e:
        if _cache["updates"] is not None:
            return _cache["updates"], None
        return [], "Couldn't load the changelog from GitHub right now."
    _cache["updates"] = updates
    _cache["at"] = now
    return updates, None
