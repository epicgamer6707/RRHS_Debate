"""Haku.cards Playwright scraper.

A single persistent Playwright thread processes scrape tasks off a queue so the
browser is launched once and reused across requests. Results are streamed back
through a per-request queue.
"""
from playwright.sync_api import sync_playwright
from urllib.parse import quote_plus
import threading
import queue as q_mod
import atexit

_task_queue = q_mod.Queue()
_pw_thread = None

CLIPBOARD_JS = """
async () => {
    const r = { text: "", html: "" };
    try {
        const items = await navigator.clipboard.read();
        for (const item of items) {
            if (item.types.includes("text/plain"))
                r.text = await (await item.getType("text/plain")).text();
            if (item.types.includes("text/html"))
                r.html = await (await item.getType("text/html")).text();
        }
    } catch (e) { r.text = "Clipboard error: " + e; }
    return r;
}
"""


def _scrape(page, query, year, event, out_q):
    url = "https://haku.cards/search?q=" + quote_plus(query)
    page.goto(url, wait_until="networkidle")

    # ── year filter ───────────────────────────────────────────────────────────
    if year != "all":
        try:
            page.click("button[aria-haspopup='dialog']")
            page.wait_for_timeout(800)
            clicked = page.evaluate("""
                (yr) => {
                    const all = Array.from(document.querySelectorAll('button'));
                    const match = all.find(b =>
                        !b.hasAttribute('aria-haspopup') &&
                        b.textContent.trim() === yr
                    );
                    if (match) { match.click(); return true; }
                    return false;
                }
            """, year)
            page.wait_for_timeout(700)
            print(f"[pw] year filter → {year} (clicked={clicked})", flush=True)
        except Exception as e:
            print(f"[pw] year filter error: {e}", flush=True)

    # ── event filter ──────────────────────────────────────────────────────────
    if event != "all":
        try:
            page.locator("button[role='combobox']").first.click()
            page.wait_for_timeout(800)
            clicked = page.evaluate("""
                (ev) => {
                    const opts = Array.from(document.querySelectorAll('[role="option"]'));
                    const match = opts.find(o =>
                        o.textContent.trim().toLowerCase() === ev.toLowerCase()
                    );
                    if (match) { match.click(); return true; }
                    return false;
                }
            """, event)
            page.wait_for_timeout(700)
            print(f"[pw] event filter → {event} (clicked={clicked})", flush=True)
        except Exception as e:
            print(f"[pw] event filter error: {e}", flush=True)

    # ── wait for filtered results ─────────────────────────────────────────────
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    try:
        page.wait_for_selector("button[data-search-result-id]", timeout=15000)
    except Exception:
        pass

    # ── stream cards one by one ───────────────────────────────────────────────
    card_els = page.query_selector_all("button[data-search-result-id]")
    total = len(card_els)

    if total == 0:
        out_q.put(("err", "No cards found — try different filters"))
        return

    count = 0
    for i, el in enumerate(card_els):
        out_q.put(("progress", i + 1, total))
        title = ""
        try:
            title = (el.inner_text() or "").split("\n")[0].strip()[:120]
            el.scroll_into_view_if_needed()
            el.click()
            page.wait_for_timeout(600)
            page.wait_for_selector("button[title='Copy card text']", timeout=8000)
            page.click("button[title='Copy card text']")
            page.wait_for_timeout(1000)
            cb = page.evaluate(CLIPBOARD_JS)
            out_q.put(("card", {
                "title": title,
                "text": cb.get("text", ""),
                "html": cb.get("html", ""),
            }))
        except Exception as e:
            out_q.put(("card", {
                "title": title or f"Card {i + 1}",
                "text": str(e),
                "html": "",
            }))
        count += 1

    out_q.put(("done", count))


_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)


def _fetch_html(page, url, out_q):
    """Load an arbitrary URL in the real browser and return its rendered HTML."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(600)
        html = page.content()
        out_q.put(("html", html))
    except Exception as e:
        out_q.put(("err", str(e)))


def _pw_worker():
    try:
        print("[pw] starting playwright...", flush=True)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                permissions=["clipboard-read", "clipboard-write"],
                user_agent=_UA,
            )
            page = ctx.new_page()
            print("[pw] ready.", flush=True)
            while True:
                job = _task_queue.get()
                if job is None:
                    break
                out_q = job["out_q"]
                try:
                    if job["kind"] == "scrape":
                        _scrape(page, job["query"], job["year"], job["event"], out_q)
                    elif job["kind"] == "fetch":
                        _fetch_html(page, job["url"], out_q)
                except Exception as e:
                    print(f"[pw] job error: {e}", flush=True)
                    out_q.put(("err", str(e)))
    except Exception as e:
        print(f"[pw] WORKER CRASHED: {e}", flush=True)
        while True:
            try:
                job = _task_queue.get_nowait()
                if job is None:
                    break
                job["out_q"].put(("err", f"Playwright worker crashed: {e}"))
            except Exception:
                break


def ensure_pw_thread():
    global _pw_thread
    if _pw_thread is None or not _pw_thread.is_alive():
        _pw_thread = threading.Thread(target=_pw_worker, daemon=True)
        _pw_thread.start()


def submit_scrape(query, year, event):
    """Queue a scrape job and return the per-request output queue."""
    ensure_pw_thread()
    out_q = q_mod.Queue()
    _task_queue.put({"kind": "scrape", "query": query, "year": year, "event": event, "out_q": out_q})
    return out_q


def submit_fetch(url):
    """Queue a URL fetch (real browser) and return the per-request output queue."""
    ensure_pw_thread()
    out_q = q_mod.Queue()
    _task_queue.put({"kind": "fetch", "url": url, "out_q": out_q})
    return out_q


def worker_status():
    alive = _pw_thread is not None and _pw_thread.is_alive()
    return {"thread_alive": alive, "queue_size": _task_queue.qsize()}


atexit.register(lambda: _task_queue.put(None))
