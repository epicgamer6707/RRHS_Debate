// ── Dashboard: edit record, import from Tabroom, add tournaments ───────────────
function csrfToken() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
}
function postJSON(url, body) {
    return fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        body: JSON.stringify(body || {}),
    }).then(r => r.json());
}

function dashToggleEdit() {
    const el = document.getElementById("dashEdit");
    el.hidden = !el.hidden;
    if (!el.hidden) el.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// ── First-run connect + refresh from a public Tabroom link ────────────────────
function dashConnect() {
    const url = document.getElementById("connectUrl").value.trim();
    const note = document.getElementById("connectNote");
    const btn = document.getElementById("connectBtn");
    if (!url) { note.style.color = "var(--loss)"; note.textContent = "Paste your Tabroom results link first."; note.hidden = false; return; }
    note.style.color = "var(--text-mid)";
    note.textContent = "Reading Tabroom…";
    note.hidden = false;
    btn.disabled = true;
    postJSON("/stats/connect", { url }).then(d => {
        if (!d.ok) { note.style.color = "var(--loss)"; note.textContent = d.error || "Couldn't connect."; btn.disabled = false; return; }
        note.style.color = "var(--win)";
        note.textContent = "Connected! " + d.wins + "W / " + d.losses + "L. Loading…";
        location.reload();
    }).catch(() => { note.style.color = "var(--loss)"; note.textContent = "Connect failed."; btn.disabled = false; });
}

function dashRefresh() {
    const btn = document.getElementById("refreshBtn");
    if (btn) { btn.disabled = true; btn.textContent = "Refreshing…"; }
    postJSON("/stats/refresh").then(d => {
        if (d.ok) { location.reload(); return; }
        if (btn) { btn.disabled = false; btn.textContent = "Refresh stats"; }
        alert(d.error || "Couldn't refresh from Tabroom.");
    }).catch(() => { if (btn) { btn.disabled = false; btn.textContent = "Refresh stats"; } });
}

function dashImport() {
    const url = document.getElementById("tabUrl").value.trim();
    const note = document.getElementById("importNote");
    if (!url) { note.style.color = "var(--loss)"; note.textContent = "Paste your Tabroom link first."; note.hidden = false; return; }
    note.style.color = "var(--text-mid)";
    note.textContent = "Reading Tabroom…";
    note.hidden = false;
    postJSON("/stats/import", { url }).then(d => {
        if (!d.ok) { note.style.color = "var(--loss)"; note.textContent = d.error || "Couldn't import."; return; }
        document.getElementById("winsIn").value = d.wins;
        document.getElementById("lossesIn").value = d.losses;
        note.style.color = "var(--win)";
        note.textContent = "Imported " + d.wins + "W / " + d.losses + "L. Check it, then Save.";
    }).catch(() => { note.style.color = "var(--loss)"; note.textContent = "Import failed."; });
}

function dashSave() {
    postJSON("/stats/update", {
        wins: document.getElementById("winsIn").value,
        losses: document.getElementById("lossesIn").value,
        tabroom_url: document.getElementById("tabUrl").value.trim(),
    }).then(d => { if (d.ok) location.reload(); });
}

function dashAddTournament() {
    const name = document.getElementById("tName").value.trim();
    if (!name) return;
    postJSON("/stats/tournament", {
        name,
        date: document.getElementById("tDate").value.trim(),
        wins: document.getElementById("tWins").value,
        losses: document.getElementById("tLosses").value,
        place: document.getElementById("tPlace").value.trim(),
    }).then(d => { if (d.ok) location.reload(); });
}

function dashDelTournament(id) {
    if (!confirm("Remove this tournament? Its wins/losses come out of your totals.")) return;
    postJSON(`/stats/tournament/${id}/delete`).then(d => { if (d.ok) location.reload(); });
}
