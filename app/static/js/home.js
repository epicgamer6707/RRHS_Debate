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

// ── Tabroom sign-in flow: credentials → "is this you?" → linked ───────────────
function dashUsePublic() {
    document.getElementById("tabStep1").hidden = true;
    document.getElementById("tabPublic").hidden = false;
}
function dashUseSignin() {
    document.getElementById("tabPublic").hidden = true;
    document.getElementById("tabStep1").hidden = false;
}

function dashTabLogin() {
    const email = document.getElementById("tabEmail").value.trim();
    const pass = document.getElementById("tabPass").value;
    const note = document.getElementById("tabNote");
    const btn = document.getElementById("tabLoginBtn");
    if (!email || !pass) { note.style.color = "var(--loss)"; note.textContent = "Enter your Tabroom email and password."; note.hidden = false; return; }
    note.style.color = "var(--text-mid)"; note.textContent = "Signing in to Tabroom…"; note.hidden = false;
    btn.disabled = true;
    postJSON("/stats/tabroom/login", { email, password: pass }).then(d => {
        document.getElementById("tabPass").value = "";   // don't leave it in the DOM
        btn.disabled = false;
        if (!d.ok) { note.style.color = "var(--loss)"; note.textContent = d.error || "Couldn't sign in."; return; }
        note.hidden = true;
        // show the "is this you?" step
        const name = d.name || "Your Tabroom account";
        document.getElementById("tabWhoName").textContent = name;
        document.getElementById("tabWhoSchool").textContent = d.school || "";
        document.getElementById("tabAvatar").textContent = (name.trim()[0] || "?").toUpperCase();
        document.getElementById("tabStep1").hidden = true;
        document.getElementById("tabStep2").hidden = false;
    }).catch(() => { btn.disabled = false; note.style.color = "var(--loss)"; note.textContent = "Sign-in failed."; });
}

function dashTabConfirm(yes) {
    const note = document.getElementById("tabNote2");
    document.getElementById("tabYesBtn").disabled = true;
    note.style.color = "var(--text-mid)"; note.textContent = yes ? "Linking…" : "Discarding…"; note.hidden = false;
    postJSON("/stats/tabroom/confirm", { confirm: yes }).then(d => {
        if (d.ok && d.linked) { location.reload(); return; }
        if (d.ok && !d.linked) {  // said "No" → back to step 1
            document.getElementById("tabStep2").hidden = true;
            document.getElementById("tabStep1").hidden = false;
            document.getElementById("tabYesBtn").disabled = false;
            note.hidden = true;
            return;
        }
        note.style.color = "var(--loss)"; note.textContent = d.error || "Couldn't link.";
        document.getElementById("tabYesBtn").disabled = false;
    }).catch(() => { note.style.color = "var(--loss)"; note.textContent = "Failed."; document.getElementById("tabYesBtn").disabled = false; });
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
