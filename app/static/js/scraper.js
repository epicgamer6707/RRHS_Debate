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

// ── AI-assisted search (runs in the visitor's browser, no server cost) ─────────
async function aiAssistSearch() {
    const input = document.getElementById("query");
    const statusEl = document.getElementById("aiSearchStatus");
    const btn = document.getElementById("aiBtn");
    const request = input.value.trim();
    if (!request) return;

    window.RRHSAI.bindStatus(statusEl);
    btn.disabled = true;
    statusEl.textContent = "Thinking…";
    try {
        const keywords = await window.RRHSAI.ask(
            `Turn this debate research request into 2-5 short search keywords for an ` +
            `evidence search engine. Keep debate shorthand (e.g. "AT" = answers-to, ` +
            `"K" = kritik, "CP" = counterplan, "DA" = disadvantage, "PIC"). No ` +
            `punctuation, no quotes, no explanation.\nRequest: ${request}`,
            "You are a policy debate research assistant. Reply with ONLY the keywords."
        );
        const cleaned = keywords.trim().replace(/["'.]/g, "").split("\n")[0].slice(0, 80);
        if (cleaned) input.value = cleaned;
        statusEl.textContent = "";
        runSearch();
    } catch (e) {
        statusEl.textContent = e.message || "AI search assist failed.";
    } finally {
        btn.disabled = false;
    }
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
        '<div class="left-empty"><span>Scraping...</span></div>';
    document.getElementById("leftCount").textContent = "0";
    document.getElementById("rightPanel").innerHTML =
        '<div class="right-empty"><span>Loading...</span></div>';
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
                `<div class="right-empty"><span>${escHtml(msg.error)}</span></div>`;
            finish();
        }
    };

    src.onerror = function() {
        if (src !== currentSrc) return;
        document.getElementById("status").textContent = "Connection error. Please try again.";
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
                <div class="right-actions">
                    <button class="btn-save" id="saveBtn" onclick="saveCard(${idx})">
                        <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
                            <path d="M3 2a1 1 0 00-1 1v11.5a.5.5 0 00.79.407L8 11.118l5.21 3.789A.5.5 0 0014 14.5V3a1 1 0 00-1-1H3z"/>
                        </svg>
                        Save
                    </button>
                    <button class="btn-copy" id="copyBtn" onclick="copyCard(${idx})">
                        <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
                            <path d="M4 4v-2.5A1.5 1.5 0 015.5 0h7A1.5 1.5 0 0114 1.5v10A1.5 1.5 0 0112.5 13H11v1.5A1.5 1.5 0 019.5 16h-6A1.5 1.5 0 012 14.5v-9A1.5 1.5 0 013.5 4H4zm1.5 0h4A1.5 1.5 0 0111 5.5V11h1.5a.5.5 0 00.5-.5v-9a.5.5 0 00-.5-.5h-7a.5.5 0 00-.5.5V4zM3.5 5a.5.5 0 00-.5.5v9a.5.5 0 00.5.5h6a.5.5 0 00.5-.5v-9a.5.5 0 00-.5-.5h-6z"/>
                        </svg>
                        Copy
                    </button>
                </div>
            </div>
            <div class="right-content">${card.html || escHtml(card.text)}</div>
        </div>`;

    applyFormat();
}

// ── copy (rich HTML so highlights/underline/bold paste into docs) ───────────────
function copyRich(html, plain) {
    try {
        if (navigator.clipboard && window.ClipboardItem) {
            const item = new ClipboardItem({
                "text/html": new Blob([html], { type: "text/html" }),
                "text/plain": new Blob([plain], { type: "text/plain" }),
            });
            return navigator.clipboard.write([item]);
        }
    } catch (e) { /* fall through to plain */ }
    return navigator.clipboard.writeText(plain);
}

function copyCard(idx) {
    const card = allResults[idx];
    const html = card.html || escHtml(card.text);
    copyRich(html, card.text).then(() => {
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

// ── save to library ────────────────────────────────────────────────────────────
function csrfToken() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
}

function saveCard(idx) {
    const card = allResults[idx];
    if (!card) return;
    const btn = document.getElementById("saveBtn");

    fetch("/library/save", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        body: JSON.stringify({ title: card.title, text: card.text, html: card.html }),
    })
    .then(r => r.json())
    .then(data => {
        if (!btn) return;
        if (data.ok) {
            btn.classList.add("saved");
            btn.innerHTML = `
                <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" fill="white">
                    <path d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z"/>
                </svg>
                Saved`;
            btn.disabled = true;
        } else {
            btn.textContent = data.error || "Error";
        }
    })
    .catch(() => { if (btn) btn.textContent = "Error"; });
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
