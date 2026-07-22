// ── Source Analyzer: one combined view. Give a source + idea, get a tagline,
//    a breakdown pie chart, the highlighted source, and an ephemeral bot. ────────
let anSrcMode = "url";
let anLoadedText = "";
let anSegments = [];
let botHistory = [];

const ROLE_COLORS = {
    warrant: "#34d39a", interp: "#2e9cca", link: "#9b8cff",
    impact: "#ff6b7d", uniqueness: "#f5c451", context: "#aaabb8",
};
const ROLE_ORDER = ["warrant", "impact", "link", "interp", "uniqueness", "context"];

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

// ── source mode toggle ──────────────────────────────────────────────────────────
function anMode(m) {
    anSrcMode = m;
    document.querySelectorAll(".an-mode").forEach(b => b.classList.toggle("active", b.dataset.m === m));
    document.getElementById("srcText").hidden = m !== "text";
    document.getElementById("srcUrl").hidden = m !== "url";
    document.getElementById("srcFileWrap").hidden = m !== "file";
}

// ── pull the raw text out of whatever the user gave us ──────────────────────────
function extractSource() {
    if (anSrcMode === "text") {
        const t = document.getElementById("srcText").value.trim();
        return t ? Promise.resolve({ ok: true, text: t }) : Promise.resolve({ ok: false, error: "Paste some text first." });
    }
    const fd = new FormData();
    if (anSrcMode === "url") {
        const u = document.getElementById("srcUrl").value.trim();
        if (!u) return Promise.resolve({ ok: false, error: "Paste a link first." });
        fd.append("url", u);
    } else {
        const f = document.getElementById("srcFile").files[0];
        if (!f) return Promise.resolve({ ok: false, error: "Choose a file first." });
        fd.append("file", f);
    }
    return fetch("/cutter/extract", { method: "POST", headers: { "X-CSRFToken": csrfToken() }, body: fd })
        .then(r => r.json());
}

// ── run the whole analysis ──────────────────────────────────────────────────────
function anRun() {
    const note = document.getElementById("srcNote");
    const btn = document.getElementById("analyzeBtn");
    const idea = document.getElementById("ideaInput").value.trim();
    if (!idea) { note.textContent = "Type your idea first — the analysis is built around it."; return; }

    btn.disabled = true; note.textContent = "Reading the source…";
    extractSource()
        .then(d => {
            if (!d.ok) throw new Error(d.error || "Couldn't load the source.");
            anLoadedText = d.text;
            note.textContent = "Analyzing against your idea…";
            return postJSON("/ai/analyze", { text: anLoadedText, idea });
        })
        .then(d => {
            if (!d.ok) throw new Error(d.error || "Analysis failed.");
            anSegments = d.segments || [];
            note.textContent = "";
            renderResults(d.tagline || "", anSegments);
        })
        .catch(e => { note.textContent = e.message || "Something went wrong."; })
        .finally(() => { btn.disabled = false; });
}

// ── render tagline + chart + highlighted source, reveal the bot ─────────────────
function renderResults(tagline, segments) {
    document.getElementById("anSetup").hidden = true;
    document.getElementById("anResults").hidden = false;

    // tagline
    const tagEl = document.getElementById("anTagline");
    if (tagline) {
        tagEl.hidden = false;
        tagEl.innerHTML = `<span class="an-tagline-label">Tagline</span>${esc(tagline)}`;
    } else { tagEl.hidden = true; }

    // breakdown counts
    const counts = {};
    segments.forEach(s => { const r = (s.role || "context"); counts[r] = (counts[r] || 0) + 1; });
    renderChart(counts);

    // highlighted source
    renderDoc(segments);

    // reset bot for this source
    botHistory = [];
    document.getElementById("botMsgs").innerHTML =
        '<div class="bot-hint">Ask about this source, e.g. "find the exact warrant", "make a tagline".</div>';
}

function anResetView() {
    document.getElementById("anResults").hidden = true;
    document.getElementById("anSetup").hidden = false;
    document.getElementById("srcNote").textContent = "";
}

// ── pie chart (pure SVG, no libraries) ──────────────────────────────────────────
function renderChart(counts) {
    const roles = ROLE_ORDER.filter(r => counts[r]);
    const total = roles.reduce((a, r) => a + counts[r], 0);
    const chart = document.getElementById("anChart");
    const legend = document.getElementById("anLegend");

    if (!total) {
        chart.innerHTML = '<div class="an-note">No labeled parts found.</div>';
        legend.innerHTML = "";
        return;
    }

    const cx = 80, cy = 80, r = 70;
    let a0 = -Math.PI / 2;
    let paths = "";
    roles.forEach(role => {
        const frac = counts[role] / total;
        const a1 = a0 + frac * 2 * Math.PI;
        if (roles.length === 1) {
            paths = `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${ROLE_COLORS[role]}"/>`;
        } else {
            const x0 = cx + r * Math.cos(a0), y0 = cy + r * Math.sin(a0);
            const x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
            const large = frac > 0.5 ? 1 : 0;
            paths += `<path d="M${cx},${cy} L${x0.toFixed(2)},${y0.toFixed(2)} A${r},${r} 0 ${large} 1 ${x1.toFixed(2)},${y1.toFixed(2)} Z" fill="${ROLE_COLORS[role]}" data-role="${role}"/>`;
        }
        a0 = a1;
    });
    chart.innerHTML =
        `<svg viewBox="0 0 160 160" width="160" height="160">${paths}
           <circle cx="${cx}" cy="${cy}" r="34" fill="var(--surface-1)"/>
           <text x="${cx}" y="${cy - 4}" text-anchor="middle" class="an-chart-num">${total}</text>
           <text x="${cx}" y="${cy + 12}" text-anchor="middle" class="an-chart-lbl">parts</text>
         </svg>`;

    legend.innerHTML = roles.map(role =>
        `<div class="an-leg-item" data-role="${role}" onmouseenter="flashRole('${role}',true)" onmouseleave="flashRole('${role}',false)">
            <span class="an-leg-dot" style="background:${ROLE_COLORS[role]}"></span>
            <span class="an-leg-name">${role}</span>
            <span class="an-leg-count">${counts[role]}</span>
         </div>`).join("");
}

// ── highlighted source document + side notes that reveal on scroll ──────────────
let anNoteObserver = null;

function renderDoc(segments) {
    // Wrap each found quote with an indexed <mark>; keep only the ones we can place.
    let html = esc(anLoadedText);
    const placed = [];
    segments.forEach((s) => {
        const q = esc((s.quote || "").trim());
        if (!q) return;
        const idx = html.indexOf(q);
        if (idx === -1) return;
        const i = placed.length;
        const role = esc(s.role || "context");
        html = html.slice(0, idx) +
            `<mark class="seg role-${role}" data-role="${role}" data-i="${i}">${q}` +
            `<span class="seg-tag">${role}</span></mark>` +
            html.slice(idx + q.length);
        placed.push({ role, note: s.note || "" });
    });
    document.getElementById("anDoc").innerHTML = html;

    // Build the side notes (one per placed segment).
    const notesEl = document.getElementById("anNotes");
    notesEl.innerHTML = placed.map((s, i) =>
        `<div class="an-note-card role-${esc(s.role)}" data-i="${i}"
              onmouseenter="flashSeg(${i}, true)" onmouseleave="flashSeg(${i}, false)">
            <span class="an-note-role">${esc(s.role)}</span>
            <div class="an-note-text">${esc(s.note)}</div>
         </div>`).join("");

    placeNotes();
    observeNotes();
}

// Position each note next to its highlight, then reveal it once scrolled into view.
function placeNotes() {
    const doc = document.getElementById("anDoc");
    const notesEl = document.getElementById("anNotes");
    if (!doc || !notesEl) return;
    const notesTop = notesEl.getBoundingClientRect().top;
    let lastBottom = -Infinity;
    notesEl.querySelectorAll(".an-note-card").forEach(card => {
        const mark = doc.querySelector(`.seg[data-i="${card.dataset.i}"]`);
        if (!mark) return;
        let top = mark.getBoundingClientRect().top - notesTop;
        if (top < lastBottom + 8) top = lastBottom + 8;  // avoid overlap
        card.style.top = Math.max(0, top) + "px";
        lastBottom = top + card.offsetHeight;
    });
    // grow the column so a tall notes stack doesn't spill past the card
    notesEl.style.minHeight = lastBottom > 0 ? lastBottom + "px" : "";
}

function observeNotes() {
    if (anNoteObserver) anNoteObserver.disconnect();
    anNoteObserver = new IntersectionObserver((entries) => {
        entries.forEach(e => {
            if (!e.isIntersecting) return;
            const i = e.target.dataset.i;
            const card = document.querySelector(`.an-note-card[data-i="${i}"]`);
            if (card) card.classList.add("show");
        });
    }, { rootMargin: "0px 0px -25% 0px" });
    document.querySelectorAll("#anDoc .seg").forEach(m => anNoteObserver.observe(m));
}

// keep notes aligned if the layout reflows
window.addEventListener("resize", () => { if (!document.getElementById("anResults").hidden) placeNotes(); });

function flashRole(role, on) {
    document.querySelectorAll(`.seg[data-role="${role}"]`).forEach(e => e.classList.toggle("flash", on));
    document.querySelectorAll(`.an-leg-item[data-role="${role}"]`).forEach(e => e.classList.toggle("flash", on));
}

function flashSeg(i, on) {
    const m = document.querySelector(`.seg[data-i="${i}"]`);
    if (m) m.classList.toggle("flash", on);
    const c = document.querySelector(`.an-note-card[data-i="${i}"]`);
    if (c) c.classList.toggle("hot", on);
}

// ── Bot (ephemeral chat) ────────────────────────────────────────────────────────
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

// ── auto-fill the source from a card handed off by Card Finder ───────────────────
(function () {
    let stashed;
    try { stashed = sessionStorage.getItem("analyzerCard"); } catch (e) { return; }
    if (!stashed) return;
    sessionStorage.removeItem("analyzerCard");
    let card;
    try { card = JSON.parse(stashed); } catch (e) { return; }
    if (!card || !card.text) return;
    anMode("text");
    document.getElementById("srcText").value = card.text;
    document.getElementById("srcNote").textContent =
        `Loaded “${(card.title || "card").slice(0, 60)}” — add your idea, then Analyze.`;
    document.getElementById("ideaInput").focus();
})();
