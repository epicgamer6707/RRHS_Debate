// ── Card Cutter: extract → cut → (optional) save to Library ────────────────────
let cutMode = "url";
let lastCut = null;

function csrfToken() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
}

function setMode(mode) {
    cutMode = mode;
    document.querySelectorAll(".cut-mode").forEach(b =>
        b.classList.toggle("active", b.dataset.mode === mode));
    document.getElementById("src-url").hidden = mode !== "url";
    document.getElementById("src-text").hidden = mode !== "text";
    document.getElementById("src-file").hidden = mode !== "file";
}

function cutCard() {
    const query = document.getElementById("cutQuery").value.trim();
    const err = document.getElementById("cutError");
    const btn = document.getElementById("cutBtn");
    err.hidden = true;
    if (!query) { showError("Type what card you want first."); return; }

    const fd = new FormData();
    fd.append("query", query);
    if (cutMode === "url") {
        const u = document.getElementById("cutUrl").value.trim();
        if (!u) { showError("Paste a link, or switch to Paste text / Upload."); return; }
        fd.append("url", u);
    } else if (cutMode === "text") {
        const t = document.getElementById("cutText").value.trim();
        if (!t) { showError("Paste some text first."); return; }
        fd.append("text", t);
    } else {
        const f = document.getElementById("cutFile").files[0];
        if (!f) { showError("Choose a file first."); return; }
        fd.append("file", f);
    }

    btn.disabled = true;
    btn.textContent = "Cutting…";

    fetch("/cutter/cut", { method: "POST", headers: { "X-CSRFToken": csrfToken() }, body: fd })
    .then(r => r.json())
    .then(data => {
        if (!data.ok) { showError(data.error || "Couldn't cut a card."); return; }
        lastCut = data;
        document.getElementById("resTag").value = data.tag || "";
        document.getElementById("resCite").value = data.citation || "";
        document.getElementById("resBody").innerHTML = data.passage_html || "";
        document.getElementById("cutNote").hidden = true;
        document.getElementById("cutResult").hidden = false;
        if (!data.matched) {
            showError("No strong match for those words. Showing the opening passage; try different keywords.");
        }
    })
    .catch(() => showError("Something went wrong. Try again."))
    .finally(() => { btn.disabled = false; btn.textContent = "Cut card"; });

    function showError(msg) { err.textContent = msg; err.hidden = false; }
}

function escHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function saveCut() {
    if (!lastCut) return;
    const tag = document.getElementById("resTag").value.trim() || lastCut.tag;
    const citation = document.getElementById("resCite").value.trim();
    const btn = document.getElementById("saveCutBtn");
    const note = document.getElementById("cutNote");
    btn.disabled = true;

    const html = `<p><strong>${escHtml(tag)}</strong></p>` +
                 `<p>${escHtml(citation)}</p>` +
                 `<p>${lastCut.passage_html}</p>`;
    const text = `${tag}\n\n${citation}\n\n${lastCut.passage_text}`;

    fetch("/library/save", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        body: JSON.stringify({ title: tag, text: text, html: html }),
    })
    .then(r => r.json())
    .then(data => {
        if (data.ok) {
            btn.textContent = "Saved";
            note.textContent = "Saved to your Library.";
            note.hidden = false;
        } else {
            note.textContent = data.error || "Couldn't save.";
            note.hidden = false;
            btn.disabled = false;
        }
    })
    .catch(() => { note.textContent = "Couldn't save."; note.hidden = false; btn.disabled = false; });
}

// ── AI analysis (runs in the visitor's own browser, no server cost) ────────────
async function analyzeWithAI() {
    if (!lastCut) return;
    const statusEl = document.getElementById("aiStatus");
    const out = document.getElementById("aiOutput");
    window.RRHSAI.bindStatus(statusEl);

    const contention = document.getElementById("aiContention").value.trim();
    const tag = document.getElementById("resTag").value.trim() || lastCut.tag;

    out.hidden = true;
    statusEl.textContent = "Thinking…";

    let prompt =
        `You are helping a policy/LD debate student understand a piece of evidence.\n\n` +
        `Tag: ${tag}\nPassage: ${lastCut.passage_text}\n\n` +
        `Explain in plain terms what this evidence argues and what its warrant (reasoning) is.`;
    if (contention) {
        prompt += `\n\nThe student wants to use it for this contention/argument: "${contention}". ` +
            `Evaluate how strongly this evidence actually links to and warrants that contention, ` +
            `and note any gaps.`;
    }

    try {
        const answer = await window.RRHSAI.ask(prompt,
            "You are a concise, accurate debate coach. Use short paragraphs, no markdown symbols.");
        out.textContent = answer;
        out.hidden = false;
        statusEl.textContent = "";
    } catch (e) {
        statusEl.textContent = e.message || "AI analysis failed.";
    }
}
