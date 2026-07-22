// ── Card Analyzer: load a card, Analyze (annotated), or Bot (ephemeral chat) ───
let anSrcMode = "text";
let anLoadedText = "";
let botHistory = [];

function csrfToken() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
}
function esc(s) {
    return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function postJSON(url, body) {
    return fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        body: JSON.stringify(body),
    }).then(r => r.json());
}

// ── source loader ─────────────────────────────────────────────────────────────
function anMode(m) {
    anSrcMode = m;
    document.querySelectorAll(".an-mode").forEach(b => b.classList.toggle("active", b.dataset.m === m));
    document.getElementById("srcText").hidden = m !== "text";
    document.getElementById("srcUrl").hidden = m !== "url";
    document.getElementById("srcFileWrap").hidden = m !== "file";
}

function anLoad() {
    const note = document.getElementById("srcNote");
    const btn = document.getElementById("loadBtn");
    const fd = new FormData();
    if (anSrcMode === "text") {
        const t = document.getElementById("srcText").value.trim();
        if (!t) { note.textContent = "Paste some text first."; return; }
        fd.append("text", t);
    } else if (anSrcMode === "url") {
        const u = document.getElementById("srcUrl").value.trim();
        if (!u) { note.textContent = "Paste a link first."; return; }
        fd.append("url", u);
    } else {
        const f = document.getElementById("srcFile").files[0];
        if (!f) { note.textContent = "Choose a file first."; return; }
        fd.append("file", f);
    }
    btn.disabled = true; note.textContent = "Loading…";
    fetch("/cutter/extract", { method: "POST", headers: { "X-CSRFToken": csrfToken() }, body: fd })
        .then(r => r.json())
        .then(d => {
            if (!d.ok) { note.textContent = d.error || "Couldn't load."; return; }
            anLoadedText = d.text;
            note.textContent = "Card loaded (" + d.text.length + " chars).";
            document.getElementById("anTabs").hidden = false;
            anTab("analyzer");
            botHistory = [];
            document.getElementById("botMsgs").innerHTML =
                '<div class="bot-hint">Ask about this card, e.g. "find the exact warrant", "make a tagline".</div>';
        })
        .catch(() => { note.textContent = "Something went wrong."; })
        .finally(() => { btn.disabled = false; });
}

function anTab(t) {
    document.querySelectorAll(".an-tab").forEach(b => b.classList.toggle("active", b.dataset.t === t));
    document.getElementById("anAnalyzer").hidden = t !== "analyzer";
    document.getElementById("anBot").hidden = t !== "bot";
}

// ── Analyzer (annotated highlights + side callouts) ────────────────────────────
function anAnalyze() {
    if (!anLoadedText) return;
    const status = document.getElementById("anStatus");
    const btn = document.getElementById("analyzeBtn");
    const idea = document.getElementById("ideaInput").value.trim();
    status.textContent = "Analyzing…"; btn.disabled = true;
    document.getElementById("anResult").innerHTML = "";
    postJSON("/ai/analyze", { text: anLoadedText, idea })
        .then(d => {
            if (!d.ok) { status.textContent = d.error || "Analysis failed."; return; }
            status.textContent = "";
            renderAnalysis(d.segments || []);
        })
        .catch(() => { status.textContent = "Something went wrong."; })
        .finally(() => { btn.disabled = false; });
}

function renderAnalysis(segments) {
    const el = document.getElementById("anResult");
    if (!segments.length) { el.innerHTML = '<div class="an-note">No key sections found. Try rephrasing your idea.</div>'; return; }

    // Build highlighted text: wrap each segment's quote where it appears.
    let html = esc(anLoadedText);
    segments.forEach((s, i) => {
        const q = esc((s.quote || "").trim());
        if (!q) return;
        const idx = html.indexOf(q);
        if (idx === -1) return;
        html = html.slice(0, idx) +
            `<mark class="seg role-${esc(s.role || "context")}" data-i="${i}">${q}</mark>` +
            html.slice(idx + q.length);
    });

    const callouts = segments.map((s, i) =>
        `<div class="callout role-${esc(s.role || "context")}" data-i="${i}"
              onmouseenter="anFlash(${i}, true)" onmouseleave="anFlash(${i}, false)">
            <span class="callout-role">${esc(s.role || "context")}</span>
            <div class="callout-note">${esc(s.note || "")}</div>
         </div>`).join("");

    el.innerHTML =
        `<div class="an-text">${html}</div>` +
        `<div class="an-callouts">${callouts}</div>`;

    el.querySelectorAll(".seg").forEach(m => {
        m.addEventListener("mouseenter", () => anFlash(m.dataset.i, true));
        m.addEventListener("mouseleave", () => anFlash(m.dataset.i, false));
    });
}

function anFlash(i, on) {
    document.querySelectorAll(`.seg[data-i="${i}"],.callout[data-i="${i}"]`)
        .forEach(e => e.classList.toggle("flash", on));
}

// ── Bot (ephemeral chat) ───────────────────────────────────────────────────────
function renderBot() {
    const box = document.getElementById("botMsgs");
    box.innerHTML = botHistory.map(m =>
        `<div class="bot-msg ${m.role}"><div class="bot-bubble">${esc(m.content)}</div></div>`).join("");
    box.scrollTop = box.scrollHeight;
}

function anSend() {
    if (!anLoadedText) return;
    const input = document.getElementById("botInput");
    const btn = document.getElementById("botSendBtn");
    const q = input.value.trim();
    if (!q) return;
    input.value = "";
    botHistory.push({ role: "user", content: q });
    botHistory.push({ role: "assistant", content: "…" });
    renderBot();
    btn.disabled = true;
    postJSON("/ai/chat", { card: anLoadedText, messages: botHistory.slice(0, -1) })
        .then(d => {
            botHistory[botHistory.length - 1] =
                { role: "assistant", content: d.ok ? d.reply : (d.error || "Couldn't answer.") };
            renderBot();
        })
        .catch(() => {
            botHistory[botHistory.length - 1] = { role: "assistant", content: "Something went wrong." };
            renderBot();
        })
        .finally(() => { btn.disabled = false; input.focus(); });
}
