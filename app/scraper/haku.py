"""Card Finder + URL fetching — pure HTTP, no browser.

Card Finder now calls haku.cards' own JSON search API directly (discovered by
watching the site's network traffic), which returns each card's citation and
per-word formatting (bold/italic/underline/highlight/size). That means we can
rebuild the highlighted cards exactly without launching a real browser — so the
whole app is light enough to run on a small, free host.

URL fetching (Card Analyzer / Citation Maker / Tabroom) also uses requests with
browser-like headers; some heavily bot-blocked sites won't return content, in
which case the tools fall back to pasted text.
"""
import queue as q_mod
from html import escape

import requests

_HL = "rgb(253,230,138)"  # same yellow the scraper/library formatting expects
_HAKU_API = "https://haku.cards/api/search"

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


# ── Card Finder (haku.cards JSON API) ─────────────────────────────────────────
def _runs_to_html(body_runs):
    parts = []
    for block in body_runs or []:
        for run in block.get("runs", []):
            text = escape(run.get("text", ""))
            if not text:
                continue
            styles = []
            if run.get("highlight"):
                styles.append(f"background-color:{_HL}")
            if run.get("bold"):
                styles.append("font-weight:700")
            if run.get("italic"):
                styles.append("font-style:italic")
            if run.get("underline"):
                styles.append("text-decoration:underline")
            sz = run.get("sz_half")
            if sz:
                styles.append(f"font-size:{sz / 2:g}pt")
            parts.append(f'<span style="{";".join(styles)}">{text}</span>' if styles else text)
    return "".join(parts)


def _year_match(hit, year):
    years = [str(y) for y in (hit.get("years") or [])]
    if hit.get("year"):
        years.append(str(hit["year"]))
    return year in years


def _search_cards(query, year, event, limit=30):
    r = requests.get(
        _HAKU_API,
        params={"q": query, "limit": limit, "offset": 0},
        headers=_BROWSER_HEADERS,
        timeout=25,
    )
    r.raise_for_status()
    hits = r.json().get("hits", [])

    cards = []
    for h in hits:
        if event != "all" and h.get("event") != event:
            continue
        if year != "all" and not _year_match(h, year):
            continue
        tag = h.get("tag") or h.get("block_title") or "Card"
        cite = h.get("cite") or ""
        body_html = _runs_to_html(h.get("body_runs"))
        html = (f"<p><strong>{escape(cite)}</strong></p>" if cite else "") + f"<p>{body_html}</p>"
        text = ((cite + "\n\n") if cite else "") + (h.get("body_text") or "")
        cards.append({"title": tag, "text": text, "html": html})
    return cards


def submit_scrape(query, year, event):
    """Queue an SSE-style result set for the Card Finder (progress/card/done)."""
    out_q = q_mod.Queue()
    try:
        cards = _search_cards(query, year, event)
        if not cards:
            out_q.put(("err", "No cards found for that search. Try different keywords, "
                              "or use Card Analyzer to build one from an article."))
        else:
            total = len(cards)
            for i, card in enumerate(cards):
                out_q.put(("progress", i + 1, total))
                out_q.put(("card", card))
            out_q.put(("done", total))
    except Exception as e:  # noqa: BLE001 — surface the failure to the user
        out_q.put(("err", f"Search failed: {e}"))
    return out_q


# ── URL fetch (Card Analyzer / Citation Maker / Tabroom) ──────────────────────
def _fetch_url(url):
    try:
        r = requests.get(url, headers=_BROWSER_HEADERS, timeout=20)
        if r.status_code < 400 and r.text:
            return r.text
    except requests.RequestException:
        pass
    try:
        import trafilatura
        return trafilatura.fetch_url(url)
    except Exception:  # noqa: BLE001
        return None


def submit_fetch(url):
    out_q = q_mod.Queue()
    html = _fetch_url(url)
    if html:
        out_q.put(("html", html))
    else:
        out_q.put(("err", "Couldn't fetch that page. Paste the text instead."))
    return out_q


def worker_status():
    return {"mode": "http", "browser": False}


def ensure_pw_thread():
    """No-op — the browser was removed. Kept so existing call sites don't break."""
    return None
