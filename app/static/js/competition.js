// ── Sign up for Competition: fetch Tabroom details, confirm, (placeholder) send ──
function csrfToken() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
}

let scraped = null;  // last successfully scraped tournament

function fetchTournament() {
    const url = document.getElementById("tabroomUrl").value.trim();
    const btn = document.getElementById("fetchBtn");
    const err = document.getElementById("fetchError");
    err.hidden = true;
    if (!url) { showError("Paste a Tabroom tournament link first."); return; }

    btn.disabled = true;
    btn.textContent = "Fetching…";

    fetch("/competition/scrape", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        body: JSON.stringify({ url }),
    })
    .then(r => r.json())
    .then(data => {
        if (!data.ok) { showError(data.error || "Couldn't fetch that tournament."); return; }
        scraped = data;
        document.getElementById("dName").textContent = data.name || "—";
        document.getElementById("dDate").textContent = data.date || "—";
        document.getElementById("dLoc").textContent = data.location || "—";
        // Pre-fill the manual fields with the scraped values.
        document.getElementById("mName").value = data.name || "";
        document.getElementById("mDate").value = data.date || "";
        document.getElementById("details").hidden = false;
        document.getElementById("sendNote").hidden = true;
    })
    .catch(() => showError("Something went wrong. Try again."))
    .finally(() => { btn.disabled = false; btn.textContent = "Fetch details"; });

    function showError(msg) { err.textContent = msg; err.hidden = false; }
}

function toggleManual() {
    const m = document.getElementById("manual");
    m.hidden = !m.hidden;
}

function sendSignup() {
    const manualShown = !document.getElementById("manual").hidden;
    const name = manualShown
        ? document.getElementById("mName").value.trim()
        : (scraped ? scraped.name : "");
    const date = manualShown
        ? document.getElementById("mDate").value.trim()
        : (scraped ? scraped.date : "");
    const event = document.getElementById("eventSel").value;
    const location = scraped ? scraped.location : "";
    const url = scraped ? scraped.url : "";

    const note = document.getElementById("sendNote");
    const btn = document.getElementById("sendBtn");
    if (!name) { note.textContent = "Add a tournament name first."; note.hidden = false; return; }

    btn.disabled = true;
    btn.textContent = "Sending…";

    fetch("/competition/send", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        body: JSON.stringify({ name, date, location, event, url }),
    })
    .then(r => r.json())
    .then(data => {
        if (!data.ok) { note.textContent = data.error || "Couldn't send."; note.hidden = false; return; }
        if (data.delivered) {
            note.innerHTML = "✅ Sent to the officers' Slack — they'll get you registered for <strong>" +
                escHtml(name) + "</strong> (" + escHtml(event) + ").";
        } else {
            note.innerHTML = "✓ Confirmed, but the officers' Slack isn't set up yet, so nothing was sent.<br>" +
                "<strong>Would send:</strong> " + escHtml(name) + " · " + escHtml(date || "—") + " · " + escHtml(event);
        }
        note.hidden = false;
    })
    .catch(() => { note.textContent = "Something went wrong. Try again."; note.hidden = false; })
    .finally(() => { btn.disabled = false; btn.textContent = "Send to officers"; });
}

function escHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
