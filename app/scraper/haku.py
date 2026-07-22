"""Haku.cards Playwright scraper + general-purpose URL fetcher.

Two independent Playwright workers, each with its own thread and browser:
  * scrape worker — searches haku.cards for the Card Finder tool. Reuses one
    page across jobs (always the same site, so this is safe and fast).
  * fetch worker — loads arbitrary user-submitted URLs (Card Cutter, Citation
    Maker). Each job gets a brand-new, isolated browser context that is always
    closed afterward.

Keeping these separate matters: a slow or heavy link pasted into the Card
Cutter can never back up or crash the Card Finder, and a fetch job's memory is
always released when its context closes instead of accumulating in one
long-lived page.
"""
from playwright.sync_api import sync_playwright
from urllib.parse import quote_plus
import threading
import queue as q_mod
import atexit

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)

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


def _drain(q, msg):
    """Flush a queue on worker crash, telling every waiting request why."""
    while True:
        try:
            job = q.get_nowait()
            if job is None:
                break
            job["out_q"].put(("err", msg))
        except Exception:
            break


# ── Card Finder (search haku.cards) ─────────────────────────────────────────
_scrape_queue = q_mod.Queue()
_scrape_thread = None


def _scrape(page, query, year, event, out_q):
    url = "https://haku.cards/search?q=" + quote_plus(query)
    page.goto(url, wait_until="networkidle", timeout=20000)

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
        out_q.put(("err", "No cards found for that search. Try different keywords, or use Card Analyzer to build one from an article."))
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


def _scrape_worker():
    try:
        print("[pw] scrape worker starting...", flush=True)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            ctx = browser.new_context(
                permissions=["clipboard-read", "clipboard-write"],
                user_agent=_UA,
            )
            page = ctx.new_page()
            print("[pw] scrape worker ready.", flush=True)
            while True:
                job = _scrape_queue.get()
                if job is None:
                    break
                out_q = job["out_q"]
                try:
                    _scrape(page, job["query"], job["year"], job["event"], out_q)
                except Exception as e:
                    print(f"[pw] scrape job error: {e}", flush=True)
                    out_q.put(("err", str(e)))
    except Exception as e:
        print(f"[pw] SCRAPE WORKER CRASHED: {e}", flush=True)
        _drain(_scrape_queue, f"Search worker crashed: {e}")


def _ensure_scrape_thread():
    global _scrape_thread
    if _scrape_thread is None or not _scrape_thread.is_alive():
        _scrape_thread = threading.Thread(target=_scrape_worker, daemon=True)
        _scrape_thread.start()


def submit_scrape(query, year, event):
    """Queue a scrape job and return the per-request output queue."""
    _ensure_scrape_thread()
    out_q = q_mod.Queue()
    _scrape_queue.put({"query": query, "year": year, "event": event, "out_q": out_q})
    return out_q


# ── general URL fetch (Card Cutter / Citation Maker) ────────────────────────
# Every job gets its own fresh context, closed right after — memory can never
# accumulate here, and a slow/heavy page can't block anything else.
_FETCH_TIMEOUT_MS = 20000
_FETCH_MAX_PENDING = 6  # reject new jobs past this backlog instead of piling up

_fetch_queue = q_mod.Queue()
_fetch_thread = None
_fetch_pending = 0
_fetch_lock = threading.Lock()


def _fetch_html(browser, url, out_q):
    ctx = None
    try:
        ctx = browser.new_context(user_agent=_UA)
        ctx.set_default_timeout(_FETCH_TIMEOUT_MS)
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=_FETCH_TIMEOUT_MS)
        page.wait_for_timeout(500)
        out_q.put(("html", page.content()))
    except Exception as e:
        out_q.put(("err", str(e)))
    finally:
        if ctx is not None:
            try:
                ctx.close()
            except Exception:
                pass


def _fetch_worker():
    global _fetch_pending
    try:
        print("[pw] fetch worker starting...", flush=True)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            print("[pw] fetch worker ready.", flush=True)
            while True:
                job = _fetch_queue.get()
                if job is None:
                    break
                try:
                    _fetch_html(browser, job["url"], job["out_q"])
                except Exception as e:
                    print(f"[pw] fetch job error: {e}", flush=True)
                    job["out_q"].put(("err", str(e)))
                finally:
                    with _fetch_lock:
                        _fetch_pending = max(0, _fetch_pending - 1)
    except Exception as e:
        print(f"[pw] FETCH WORKER CRASHED: {e}", flush=True)
        _drain(_fetch_queue, f"Fetch worker crashed: {e}")


def _ensure_fetch_thread():
    global _fetch_thread
    if _fetch_thread is None or not _fetch_thread.is_alive():
        _fetch_thread = threading.Thread(target=_fetch_worker, daemon=True)
        _fetch_thread.start()


def submit_fetch(url):
    """Queue a URL fetch; returns the output queue, or None if overloaded."""
    global _fetch_pending
    _ensure_fetch_thread()
    with _fetch_lock:
        if _fetch_pending >= _FETCH_MAX_PENDING:
            return None
        _fetch_pending += 1
    out_q = q_mod.Queue()
    _fetch_queue.put({"url": url, "out_q": out_q})
    return out_q


def worker_status():
    return {
        "scrape_alive": _scrape_thread is not None and _scrape_thread.is_alive(),
        "fetch_alive": _fetch_thread is not None and _fetch_thread.is_alive(),
        "scrape_queue": _scrape_queue.qsize(),
        "fetch_queue": _fetch_queue.qsize(),
    }


def ensure_pw_thread():
    """Eagerly start the scrape worker (kept for existing call sites)."""
    _ensure_scrape_thread()


atexit.register(lambda: (_scrape_queue.put(None), _fetch_queue.put(None)))
