// ── Sign up for Competition: manual details (Tabroom link optional) ────────────
function csrfToken() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
}

let scrapedUrl = "";

function fetchTournament() {
    const url = document.getElementById("tabroomUrl").value.trim();
    const btn = document.getElementById("fetchBtn");
    const err = document.getElementById("fetchError");
    const note = document.getElementById("fetchNote");
    err.hidden = true;
    note.hidden = true;
    if (!url) { showError("Paste a Tabroom link, or just type the details below."); return; }

    btn.disabled = true;
    btn.textContent = "Fetching...";

    fetch("/competition/scrape", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        body: JSON.stringify({ url }),
    })
    .then(r => r.json())
    .then(data => {
        if (!data.ok) { showError(data.error || "Couldn't fetch that tournament."); return; }
        scrapedUrl = data.url || url;
        if (data.name) document.getElementById("mName").value = data.name;
        if (data.date) document.getElementById("mDate").value = data.date;
        if (data.location) document.getElementById("mLoc").value = data.location;
        note.textContent = "Filled in from Tabroom. Check the details below, then send.";
        note.hidden = false;
    })
    .catch(() => showError("Something went wrong. Try again."))
    .finally(() => { btn.disabled = false; btn.textContent = "Fetch details"; });

    function showError(msg) { err.textContent = msg; err.hidden = false; }
}

function sendSignup() {
    const name = document.getElementById("mName").value.trim();
    const date = document.getElementById("mDate").value.trim();
    const location = document.getElementById("mLoc").value.trim();
    const event = document.getElementById("eventSel").value;
    const note = document.getElementById("sendNote");
    const btn = document.getElementById("sendBtn");

    if (!name) { note.textContent = "Add a tournament name first."; note.hidden = false; return; }

    btn.disabled = true;
    btn.textContent = "Sending...";

    fetch("/competition/send", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        body: JSON.stringify({ name, date, location, event, url: scrapedUrl }),
    })
    .then(r => r.json())
    .then(data => {
        if (!data.ok) { note.textContent = data.error || "Couldn't send."; note.hidden = false; return; }
        if (data.delivered) {
            note.innerHTML = "Sent to the officers' Slack. They'll get you registered for <strong>" +
                escHtml(name) + "</strong> (" + escHtml(event) + ").";
        } else {
            note.innerHTML = "Confirmed, but the officers' Slack isn't set up yet, so nothing was sent.<br>" +
                "<strong>Would send:</strong> " + escHtml(name) + ", " + escHtml(date || "no date") + ", " + escHtml(event);
        }
        note.hidden = false;
    })
    .catch(() => { note.textContent = "Something went wrong. Try again."; note.hidden = false; })
    .finally(() => { btn.disabled = false; btn.textContent = "Send to officers"; });
}

function escHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
