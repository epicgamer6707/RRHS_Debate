// ── Resources: render the Google Classroom feed, auto-refresh ~1 min ───────────
function csrfToken() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
}

function esc(s) {
    return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function fmtDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function attHtml(a) {
    const label = a.type === "file" ? "Download"
        : a.type === "video" ? "Video"
        : a.type === "form" ? "Form" : "Open";
    return `<a class="res-att" href="${esc(a.link)}" target="_blank" rel="noopener">${esc(label)}: ${esc(a.title)}</a>`;
}

function itemHtml(it) {
    const title = it.link
        ? `<a href="${esc(it.link)}" target="_blank" rel="noopener">${esc(it.title)}</a>`
        : esc(it.title);
    let html = `<div class="res-item"><div class="res-item-head">` +
        `<div class="res-item-title">${title}</div>` +
        `<div class="res-item-date">${esc(fmtDate(it.date))}</div></div>`;
    if (it.text) html += `<div class="res-item-text">${esc(it.text)}</div>`;
    if (it.attachments && it.attachments.length)
        html += `<div class="res-atts">${it.attachments.map(attHtml).join("")}</div>`;
    return html + `</div>`;
}

function render(feed) {
    const el = document.getElementById("resFeed");
    if (!el) return;
    if (feed.error === "reconnect") {
        el.innerHTML = `<div class="res-empty">Connection expired. Click Disconnect, then Connect again.</div>`;
        return;
    }
    let html = "";
    if (feed.stream && feed.stream.length) {
        html += `<div class="res-section"><div class="res-section-title">Stream</div>` +
            feed.stream.map(itemHtml).join("") + `</div>`;
    }
    (feed.sections || []).forEach(s => {
        if (!s.items || !s.items.length) return;
        html += `<div class="res-section"><div class="res-section-title">${esc(s.topic)}</div>` +
            s.items.map(itemHtml).join("") + `</div>`;
    });
    el.innerHTML = html || `<div class="res-empty">No posts yet.</div>`;
}

function load(force) {
    fetch("/resources/data" + (force ? "?force=1" : ""))
        .then(r => r.json())
        .then(render)
        .catch(() => {});
}

function refreshNow() { load(true); }

function disconnectClassroom() {
    if (!confirm("Disconnect Google Classroom? The Resources feed will stop until an officer reconnects.")) return;
    fetch("/resources/disconnect", { method: "POST", headers: { "X-CSRFToken": csrfToken() } })
        .then(() => location.reload());
}

load(false);
setInterval(() => load(false), 60000);
