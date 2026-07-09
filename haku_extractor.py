from flask import Flask, render_template_string, jsonify, request, Response, stream_with_context
from playwright.sync_api import sync_playwright
from urllib.parse import quote_plus
import threading
import queue as q_mod
import json
import atexit
import os

app = Flask(__name__)

_task_queue = q_mod.Queue()
_pw_thread  = None

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
    total    = len(card_els)

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
                "text":  cb.get("text", ""),
                "html":  cb.get("html", ""),
            }))
        except Exception as e:
            out_q.put(("card", {
                "title": title or f"Card {i + 1}",
                "text":  str(e),
                "html":  "",
            }))
        count += 1

    out_q.put(("done", count))


def _pw_worker():
    try:
        print("[pw] starting playwright...", flush=True)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx  = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
            page = ctx.new_page()
            print("[pw] ready.", flush=True)
            while True:
                item = _task_queue.get()
                if item is None:
                    break
                query, year, event, out_q = item
                try:
                    _scrape(page, query, year, event, out_q)
                except Exception as e:
                    print(f"[pw] scrape error: {e}", flush=True)
                    out_q.put(("err", str(e)))
    except Exception as e:
        print(f"[pw] WORKER CRASHED: {e}", flush=True)
        while True:
            try:
                item = _task_queue.get_nowait()
                if item is None:
                    break
                _, _, _, out_q = item
                out_q.put(("err", f"Playwright worker crashed: {e}"))
            except Exception:
                break


def _ensure_pw_thread():
    global _pw_thread
    if _pw_thread is None or not _pw_thread.is_alive():
        _pw_thread = threading.Thread(target=_pw_worker, daemon=True)
        _pw_thread.start()


atexit.register(lambda: _task_queue.put(None))

# ─────────────────────────────────────────────────────────────────────────────
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Debate Extractor</title>
<style>
/* ── reset & base ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
    --bg:       #f3f0e8;
    --bg-panel: #ece9e1;
    --bg-card:  #f8f6f1;
    --bg-right: #faf8f4;
    --border:   rgba(0,0,0,0.09);
    --border-md:rgba(0,0,0,0.14);
    --text:     #1c1916;
    --text-2:   #5c5751;
    --text-3:   #9a958f;
    --blue:     #2d5be3;
    --blue-lt:  #eef2ff;
    --blue-bd:  #93aef8;
    --green:    #16803c;
    --shadow-sm:0 1px 3px rgba(0,0,0,0.07);
    --shadow:   0 2px 8px rgba(0,0,0,0.10);
    --radius:   9px;
    --radius-sm:6px;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
    font-size: 13.5px;
    background: var(--bg);
    color: var(--text);
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

/* ── topbar ── */
.topbar {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 16px;
    background: var(--bg-panel);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
}

.brand {
    display: flex;
    align-items: center;
    gap: 7px;
    white-space: nowrap;
    flex-shrink: 0;
}

.brand-icon {
    width: 26px;
    height: 26px;
    background: var(--blue);
    border-radius: 7px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}

.brand-icon svg {
    width: 14px;
    height: 14px;
    fill: white;
}

.brand-name {
    font-size: 15px;
    font-weight: 700;
    letter-spacing: -0.3px;
    color: var(--text);
}

.search-wrap {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 6px;
    background: white;
    border: 1px solid var(--border-md);
    border-radius: var(--radius);
    padding: 0 6px 0 12px;
    box-shadow: var(--shadow-sm);
    transition: border-color 0.15s, box-shadow 0.15s;
}

.search-wrap:focus-within {
    border-color: var(--blue);
    box-shadow: 0 0 0 3px rgba(45,91,227,0.12);
}

.search-wrap input {
    flex: 1;
    border: none;
    outline: none;
    background: transparent;
    font-size: 14px;
    color: var(--text);
    padding: 8px 0;
    min-width: 0;
}

.search-wrap input::placeholder { color: var(--text-3); }

.btn-search {
    padding: 6px 14px;
    background: var(--blue);
    color: white;
    border: none;
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
    white-space: nowrap;
    transition: background 0.15s, opacity 0.15s;
    flex-shrink: 0;
}

.btn-search:hover { background: #1d4fd6; }
.btn-search:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-copyall {
    padding: 6px 14px;
    background: transparent;
    color: var(--green);
    border: 1px solid rgba(22,128,60,0.35);
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
    white-space: nowrap;
    display: none;
    flex-shrink: 0;
    transition: background 0.15s;
}

.btn-copyall:hover { background: rgba(22,128,60,0.07); }

/* ── filterbar ── */
.filterbar {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 7px 16px;
    background: var(--bg-panel);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
    flex-wrap: wrap;
}

.filter-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-3);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-right: 2px;
}

.fb-select {
    padding: 5px 8px;
    font-size: 12.5px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-md);
    background: white;
    color: var(--text);
    cursor: pointer;
    outline: none;
    box-shadow: var(--shadow-sm);
    transition: border-color 0.15s;
}

.fb-select:focus { border-color: var(--blue); }

.fb-divider {
    width: 1px;
    height: 20px;
    background: var(--border-md);
    margin: 0 4px;
    flex-shrink: 0;
}

.hl-group {
    display: flex;
    gap: 3px;
    align-items: center;
}

.hl-btn {
    width: 26px;
    height: 26px;
    border-radius: 5px;
    border: 2px solid transparent;
    font-size: 11px;
    font-weight: 700;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: border-color 0.12s, transform 0.1s;
    flex-shrink: 0;
}

.hl-btn:hover { transform: scale(1.1); }
.hl-btn.active { border-color: #1e3a8a; box-shadow: 0 0 0 1px #1e3a8a; }
#hlY { background: #fde68a; color: #78350f; }
#hlG { background: #bbf7d0; color: #14532d; }
#hlB { background: #bfdbfe; color: #1e3a8a; }
#hlN { background: #e5e7eb; color: #374151; font-size: 14px; line-height: 1; }

.var-label {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 12px;
    color: var(--text-2);
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
}

.var-label input[type="checkbox"] { cursor: pointer; accent-color: var(--blue); }

/* ── statusbar ── */
.statusbar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 16px;
    background: var(--bg);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
    min-height: 28px;
}

.spinner {
    display: none;
    width: 13px;
    height: 13px;
    border: 2px solid var(--border-md);
    border-top-color: var(--blue);
    border-radius: 50%;
    animation: spin 0.65s linear infinite;
    flex-shrink: 0;
}

@keyframes spin { to { transform: rotate(360deg); } }

.status-text {
    font-size: 12px;
    color: var(--text-2);
}

/* ── panels ── */
.panels {
    display: grid;
    grid-template-columns: 320px 1fr;
    flex: 1;
    overflow: hidden;
    min-height: 0;
}

/* ── left sidebar ── */
.left-panel {
    display: flex;
    flex-direction: column;
    overflow: hidden;
    border-right: 1px solid var(--border);
    background: var(--bg-panel);
}

.left-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px 8px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
}

.left-header-title {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-3);
    text-transform: uppercase;
    letter-spacing: 0.07em;
}

.left-count {
    font-size: 11px;
    color: var(--text-3);
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 1px 7px;
}

.left-scroll {
    overflow-y: auto;
    flex: 1;
    padding: 8px;
}

.left-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    height: 100%;
    color: var(--text-3);
    font-size: 13px;
    padding: 40px 20px;
    text-align: center;
}

.left-empty-icon {
    font-size: 28px;
    opacity: 0.4;
}

.card-item {
    width: 100%;
    text-align: left;
    background: white;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 10px 12px;
    margin-bottom: 5px;
    cursor: pointer;
    transition: background 0.1s, border-color 0.1s, box-shadow 0.1s;
    position: relative;
}

.card-item:hover {
    background: var(--blue-lt);
    border-color: var(--blue-bd);
    box-shadow: var(--shadow-sm);
}

.card-item.active {
    background: var(--blue-lt);
    border-color: var(--blue);
    box-shadow: 0 0 0 1px var(--blue);
}

.card-num {
    font-size: 10px;
    font-weight: 700;
    color: var(--text-3);
    margin-bottom: 3px;
    letter-spacing: 0.04em;
}

.card-item.active .card-num { color: var(--blue); }

.card-item-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text);
    line-height: 1.35;
    margin-bottom: 4px;
}

.card-item-preview {
    font-size: 11.5px;
    color: var(--text-2);
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

/* ── right panel ── */
.right-panel {
    overflow-y: auto;
    background: var(--bg-right);
    display: flex;
    flex-direction: column;
}

.right-empty {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
    color: var(--text-3);
    font-size: 14px;
}

.right-empty-icon { font-size: 36px; opacity: 0.3; }

.right-card-wrap {
    padding: 28px 32px;
    max-width: 900px;
    width: 100%;
}

.right-meta {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border);
}

.right-title {
    font-size: 17px;
    font-weight: 700;
    color: var(--text);
    line-height: 1.35;
    flex: 1;
    letter-spacing: -0.2px;
}

.btn-copy {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 7px 14px;
    background: var(--text);
    color: white;
    border: none;
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-size: 12.5px;
    font-weight: 600;
    white-space: nowrap;
    flex-shrink: 0;
    transition: background 0.15s;
}

.btn-copy:hover { background: #333; }
.btn-copy.copied { background: var(--green); }

.btn-copy svg {
    width: 13px;
    height: 13px;
    fill: currentColor;
    flex-shrink: 0;
}

.right-content {
    line-height: 1.8;
    color: var(--text);
    word-break: break-word;
}

/* format overrides injected by JS */
</style>
<style id="fmtStyle"></style>
</head>
<body>

<!-- ── topbar ── -->
<div class="topbar">
    <div class="brand">
        <div class="brand-icon">
            <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
                <path d="M2 2h12v1.5H9.5V8H7V3.5H2V2zm0 6.5h5.5V14h1V8.5H14V7H2v1.5z"/>
            </svg>
        </div>
        <span class="brand-name">Debate Extractor</span>
    </div>

    <div class="search-wrap">
        <input id="query" placeholder="Search evidence…" value="cap k"
               onkeydown="if(event.key==='Enter') runSearch()"/>
        <button class="btn-search" id="btn" onclick="runSearch()">Search</button>
    </div>

    <button class="btn-copyall" id="copyAllBtn" onclick="copyAll()">Copy All</button>
</div>

<!-- ── filterbar ── -->
<div class="filterbar">
    <span class="filter-label">Year</span>
    <select class="fb-select" id="filterYear">
        <option value="all">All</option>
        <option value="2025">2025</option>
        <option value="2024">2024</option>
        <option value="2023">2023</option>
        <option value="2022">2022</option>
        <option value="2021">2021</option>
        <option value="2020">2020</option>
        <option value="2019">2019</option>
        <option value="2018">2018</option>
        <option value="2017">2017</option>
        <option value="2016">2016</option>
        <option value="2015">2015</option>
        <option value="2014">2014</option>
        <option value="2013">2013</option>
    </select>

    <span class="filter-label" style="margin-left:4px;">Event</span>
    <select class="fb-select" id="filterEvent">
        <option value="all">All</option>
        <option value="hspolicy">HS Policy</option>
        <option value="hsld">HS LD</option>
        <option value="hspf">HS PF</option>
        <option value="ndtceda">NDT/CEDA</option>
        <option value="nfald">NFA LD</option>
    </select>

    <div class="fb-divider"></div>

    <span class="filter-label">Font</span>
    <select class="fb-select" id="fontSel" onchange="applyFormat()">
        <option value="Calibri,'Segoe UI',Arial,sans-serif">Calibri</option>
        <option value="Arial,Helvetica,sans-serif">Arial</option>
        <option value="'Times New Roman',Times,serif">Times New Roman</option>
    </select>

    <div class="fb-divider"></div>

    <span class="filter-label">Highlight</span>
    <div class="hl-group">
        <button class="hl-btn active" id="hlY" onclick="setHL('Y')" title="Yellow">Y</button>
        <button class="hl-btn"        id="hlG" onclick="setHL('G')" title="Green">G</button>
        <button class="hl-btn"        id="hlB" onclick="setHL('B')" title="Blue">B</button>
        <button class="hl-btn"        id="hlN" onclick="setHL('N')" title="No highlight">×</button>
    </div>

    <div class="fb-divider"></div>

    <label class="var-label">
        <input type="checkbox" id="varFont" checked onchange="applyFormat()">
        Variable sizes
    </label>
</div>

<!-- ── statusbar ── -->
<div class="statusbar">
    <div class="spinner" id="spinner"></div>
    <span class="status-text" id="status">Ready — enter a search above.</span>
</div>

<!-- ── panels ── -->
<div class="panels">

    <!-- left -->
    <div class="left-panel">
        <div class="left-header">
            <span class="left-header-title">Cards</span>
            <span class="left-count" id="leftCount">0</span>
        </div>
        <div class="left-scroll" id="leftPanel">
            <div class="left-empty">
                <div class="left-empty-icon">🗂</div>
                <span>Results will appear here</span>
            </div>
        </div>
    </div>

    <!-- right -->
    <div class="right-panel" id="rightPanel">
        <div class="right-empty">
            <div class="right-empty-icon">📄</div>
            <span>Select a card to read it</span>
        </div>
    </div>

</div>

<script>
let allResults = [];
let activeIdx  = -1;
let currentHL  = "Y";
let currentSrc = null;

const HL_COLORS = {
    Y: "rgb(253,230,138)",   /* fde68a */
    G: "rgb(187,247,208)",   /* bbf7d0 */
    B: "rgb(191,219,254)",   /* bfdbfe */
    N: null
};

// ── format ────────────────────────────────────────────────────────────────────
function applyFormat() {
    const font    = document.getElementById("fontSel").value;
    const varFont = document.getElementById("varFont").checked;
    let css = `.right-content * { font-family: ${font} !important; }`;
    if (!varFont) css += `\n.right-content span { font-size: 11pt !important; }`;
    document.getElementById("fmtStyle").textContent = css;

    const rc = document.querySelector(".right-content");
    if (!rc) return;
    const newColor = HL_COLORS[currentHL];
    rc.querySelectorAll("span").forEach(span => {
        const bg = span.style.backgroundColor;
        if (!bg || bg === "transparent" || bg === "") return;
        if (newColor) {
            span.style.backgroundColor = newColor;
        } else {
            span.style.removeProperty("background-color");
            span.style.removeProperty("color");
            span.style.removeProperty("padding");
            span.style.removeProperty("border-radius");
        }
    });
}

function setHL(mode) {
    currentHL = mode;
    ["Y","G","B","N"].forEach(m =>
        document.getElementById("hl"+m).classList.toggle("active", m === mode)
    );
    applyFormat();
}

// ── search ────────────────────────────────────────────────────────────────────
function runSearch() {
    const btn   = document.getElementById("btn");
    const query = document.getElementById("query").value.trim();
    if (!query) return;

    if (currentSrc) { currentSrc.close(); currentSrc = null; }

    btn.disabled = true;
    allResults = []; activeIdx = -1;

    document.getElementById("leftPanel").innerHTML =
        '<div class="left-empty"><div class="left-empty-icon">⏳</div><span>Scraping…</span></div>';
    document.getElementById("leftCount").textContent = "0";
    document.getElementById("rightPanel").innerHTML =
        '<div class="right-empty"><div class="right-empty-icon">⏳</div><span>Loading…</span></div>';
    document.getElementById("copyAllBtn").style.display = "none";
    document.getElementById("spinner").style.display = "block";
    document.getElementById("status").textContent = "Connecting to Haku…";

    const year  = document.getElementById("filterYear").value;
    const event = document.getElementById("filterEvent").value;
    const qs    = new URLSearchParams({ query, year, event });

    const src = new EventSource("/run-automation?" + qs);
    currentSrc = src;

    src.onmessage = function(e) {
        let msg;
        try { msg = JSON.parse(e.data); }
        catch(err) { console.error("SSE parse error:", err, e.data); return; }

        if (msg.type === "progress") {
            document.getElementById("status").textContent =
                `Scraping card ${msg.current} of ${msg.total}…`;

        } else if (msg.type === "result") {
            // Clear the "Scraping…" placeholder on first result
            if (allResults.length === 0) {
                document.getElementById("leftPanel").innerHTML = "";
            }
            const idx = allResults.length;
            allResults.push(msg);
            document.getElementById("leftCount").textContent = allResults.length;
            appendSidebarItem(msg, idx);
            if (idx === 0) showCard(0);

        } else if (msg.type === "done") {
            const yr  = year  === "all" ? "all years"  : year;
            const ev  = event === "all" ? "all events" : event;
            document.getElementById("status").textContent =
                `${msg.count} card${msg.count !== 1 ? "s" : ""} · ${yr} · ${ev}`;
            if (msg.count > 0)
                document.getElementById("copyAllBtn").style.display = "inline-flex";
            finish();

        } else if (msg.type === "error") {
            document.getElementById("status").textContent = "Error: " + msg.error;
            document.getElementById("rightPanel").innerHTML =
                `<div class="right-empty"><div class="right-empty-icon">⚠️</div><span>${escHtml(msg.error)}</span></div>`;
            finish();
        }
    };

    src.onerror = function() {
        if (src !== currentSrc) return;
        document.getElementById("status").textContent = "Connection error — check terminal.";
        finish();
    };

    function finish() {
        src.close();
        if (currentSrc === src) currentSrc = null;
        document.getElementById("spinner").style.display = "none";
        btn.disabled = false;
    }
}

// ── sidebar item ──────────────────────────────────────────────────────────────
function appendSidebarItem(card, idx) {
    const lines    = (card.text || "").split("\n").filter(l => l.trim());
    const preview  = lines[1] || lines[0] || "";
    const num      = String(idx + 1).padStart(2, "0");

    const el = document.createElement("button");
    el.className = "card-item";
    el.id = "item-" + idx;
    el.onclick = () => showCard(idx);
    el.innerHTML = `
        <div class="card-num">${num}</div>
        <div class="card-item-title">${escHtml(card.title || "Card " + (idx+1))}</div>
        <div class="card-item-preview">${escHtml(preview)}</div>`;
    document.getElementById("leftPanel").appendChild(el);
}

// ── right panel ───────────────────────────────────────────────────────────────
function showCard(idx) {
    const card = allResults[idx];
    if (!card) return;

    if (activeIdx >= 0) {
        const prev = document.getElementById("item-" + activeIdx);
        if (prev) prev.classList.remove("active");
    }
    activeIdx = idx;
    const cur = document.getElementById("item-" + idx);
    if (cur) { cur.classList.add("active"); cur.scrollIntoView({ block: "nearest" }); }

    document.getElementById("rightPanel").innerHTML = `
        <div class="right-card-wrap">
            <div class="right-meta">
                <div class="right-title">${escHtml(card.title || "Card " + (idx+1))}</div>
                <button class="btn-copy" id="copyBtn" onclick="copyCard(${idx})">
                    <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
                        <path d="M4 4v-2.5A1.5 1.5 0 015.5 0h7A1.5 1.5 0 0114 1.5v10A1.5 1.5 0 0112.5 13H11v1.5A1.5 1.5 0 019.5 16h-6A1.5 1.5 0 012 14.5v-9A1.5 1.5 0 013.5 4H4zm1.5 0h4A1.5 1.5 0 0111 5.5V11h1.5a.5.5 0 00.5-.5v-9a.5.5 0 00-.5-.5h-7a.5.5 0 00-.5.5V4zM3.5 5a.5.5 0 00-.5.5v9a.5.5 0 00.5.5h6a.5.5 0 00.5-.5v-9a.5.5 0 00-.5-.5h-6z"/>
                    </svg>
                    Copy
                </button>
            </div>
            <div class="right-content">${card.html || escHtml(card.text)}</div>
        </div>`;

    applyFormat();
}

// ── copy ──────────────────────────────────────────────────────────────────────
function copyCard(idx) {
    // Copy the raw markdown text exactly as Haku formatted it
    navigator.clipboard.writeText(allResults[idx].text).then(() => {
        const btn = document.getElementById("copyBtn");
        if (!btn) return;
        btn.classList.add("copied");
        btn.innerHTML = `
            <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" fill="white">
                <path d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z"/>
            </svg>
            Copied!`;
        setTimeout(() => {
            btn.classList.remove("copied");
            btn.innerHTML = `
                <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
                    <path d="M4 4v-2.5A1.5 1.5 0 015.5 0h7A1.5 1.5 0 0114 1.5v10A1.5 1.5 0 0112.5 13H11v1.5A1.5 1.5 0 019.5 16h-6A1.5 1.5 0 012 14.5v-9A1.5 1.5 0 013.5 4H4zm1.5 0h4A1.5 1.5 0 0111 5.5V11h1.5a.5.5 0 00.5-.5v-9a.5.5 0 00-.5-.5h-7a.5.5 0 00-.5.5V4zM3.5 5a.5.5 0 00-.5.5v9a.5.5 0 00.5.5h6a.5.5 0 00.5-.5v-9a.5.5 0 00-.5-.5h-6z"/>
                </svg>
                Copy`;
        }, 2000);
    });
}

function copyAll() {
    const text = allResults.map((r, i) =>
        `## Card ${i+1}: ${r.title}\n\n${r.text}`).join("\n\n---\n\n");
    navigator.clipboard.writeText(text).then(() => {
        const btn = document.getElementById("copyAllBtn");
        const orig = btn.textContent;
        btn.textContent = "Copied!";
        setTimeout(() => { btn.textContent = orig; }, 2000);
    });
}

function escHtml(s) {
    return String(s)
        .replace(/&/g,"&amp;").replace(/</g,"&lt;")
        .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}
</script>
</body>
</html>
"""

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def home():
    return render_template_string(HTML_TEMPLATE)


@app.route("/ping")
def ping():
    alive = _pw_thread is not None and _pw_thread.is_alive()
    return jsonify({"thread_alive": alive, "queue_size": _task_queue.qsize()})


@app.route("/run-automation")
def run_automation():
    query = request.args.get("query", "").strip()
    year  = request.args.get("year",  "all").strip()
    event = request.args.get("event", "all").strip()

    if not query:
        def err_gen():
            yield f'data: {json.dumps({"type": "error", "error": "No query provided"})}\n\n'
        return Response(stream_with_context(err_gen()), mimetype="text/event-stream")

    _ensure_pw_thread()

    out_q = q_mod.Queue()
    _task_queue.put((query, year, event, out_q))

    def generate():
        while True:
            try:
                item = out_q.get(timeout=60)
            except q_mod.Empty:
                yield f'data: {json.dumps({"type": "error", "error": "Timed out waiting for card"})}\n\n'
                return

            kind = item[0]
            if kind == "progress":
                _, current, total = item
                yield f'data: {json.dumps({"type": "progress", "current": current, "total": total})}\n\n'
            elif kind == "card":
                _, card = item
                card["type"] = "result"
                yield f'data: {json.dumps(card)}\n\n'
            elif kind == "done":
                _, count = item
                yield f'data: {json.dumps({"type": "done", "count": count})}\n\n'
                return
            elif kind == "err":
                _, msg = item
                yield f'data: {json.dumps({"type": "error", "error": msg})}\n\n'
                return

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    _ensure_pw_thread()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)
