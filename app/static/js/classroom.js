// ── Classroom (Classwork): render sections, post, download/open attachments ────
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

// ── compose form ─────────────────────────────────────────────────────────────
function crToggleForm() {
    const form = document.getElementById("crForm");
    form.hidden = !form.hidden;
}

function crTopicChange() {
    const sel = document.getElementById("crTopicSel");
    const nt = document.getElementById("crNewTopic");
    nt.hidden = sel.value !== "__new__";
    if (!nt.hidden) nt.focus();
}

function crAddLinkRow() {
    const wrap = document.getElementById("crLinks");
    const row = document.createElement("div");
    row.className = "cr-link-row";
    row.innerHTML =
        '<input type="text" class="cr-input" placeholder="Link title">' +
        '<input type="text" class="cr-input" placeholder="https://...">' +
        '<button type="button" class="cr-rm" onclick="this.parentElement.remove()">&times;</button>';
    wrap.appendChild(row);
}

function crSubmit() {
    const title = document.getElementById("crTitle").value.trim();
    const err = document.getElementById("crErr");
    err.hidden = true;
    if (!title) { err.textContent = "Give it a title first."; err.hidden = false; return; }

    const fd = new FormData();
    fd.append("title", title);
    fd.append("body", document.getElementById("crBody").value.trim());

    const sel = document.getElementById("crTopicSel");
    if (sel.value === "__new__") {
        const name = document.getElementById("crNewTopic").value.trim();
        if (name) fd.append("new_topic", name);
    } else if (sel.value) {
        fd.append("topic_id", sel.value);
    }

    document.querySelectorAll("#crLinks .cr-link-row").forEach(row => {
        const inputs = row.querySelectorAll("input");
        if (inputs[1].value.trim()) {
            fd.append("link_title", inputs[0].value.trim());
            fd.append("link_url", inputs[1].value.trim());
        }
    });

    const files = document.getElementById("crFiles").files;
    for (let i = 0; i < files.length; i++) fd.append("files", files[i]);

    fetch("/classroom/post", { method: "POST", headers: { "X-CSRFToken": csrfToken() }, body: fd })
        .then(r => r.json())
        .then(d => {
            if (!d.ok) { err.textContent = d.error || "Couldn't post."; err.hidden = false; return; }
            document.getElementById("crTitle").value = "";
            document.getElementById("crBody").value = "";
            document.getElementById("crLinks").innerHTML = "";
            document.getElementById("crFiles").value = "";
            sel.value = "";
            document.getElementById("crNewTopic").hidden = true;
            crToggleForm();
            load();
        })
        .catch(() => { err.textContent = "Something went wrong."; err.hidden = false; });
}

// ── render ────────────────────────────────────────────────────────────────────
function attHtml(a) {
    const label = a.kind === "link" ? "Open" : "Download";
    const target = a.kind === "link" ? ' target="_blank" rel="noopener"' : "";
    return `<a class="cr-att" href="${esc(a.url)}"${target}>${label}: ${esc(a.title)}</a>`;
}

function postHtml(p) {
    const del = window.CR_CAN_POST
        ? `<button class="cr-del" onclick="crDelete(${p.id})">Delete</button>` : "";
    const body = p.body ? `<div class="cr-post-body">${esc(p.body)}</div>` : "";
    const atts = p.attachments.length
        ? `<div class="cr-atts">${p.attachments.map(attHtml).join("")}</div>` : "";
    return `<div class="cr-post">
        <div class="cr-post-head">
          <span class="cr-post-title">${esc(p.title)}</span>
          <span class="cr-post-meta">${esc(fmtDate(p.date))} ${del}</span>
        </div>
        ${body}${atts}
      </div>`;
}

function render(data) {
    const el = document.getElementById("crFeed");
    if (!el) return;

    // populate the topic dropdown
    const sel = document.getElementById("crTopicSel");
    if (sel && data.topics) {
        const current = sel.value;
        sel.innerHTML = '<option value="">General</option>' +
            data.topics.map(t => `<option value="${t.id}">${esc(t.name)}</option>`).join("") +
            '<option value="__new__">+ New section…</option>';
        if ([...sel.options].some(o => o.value === current)) sel.value = current;
    }

    const sections = (data.sections || []).filter(s => s.posts && s.posts.length);
    if (!sections.length) {
        el.innerHTML = `<div class="cr-empty">Nothing posted yet.</div>`;
        return;
    }
    el.innerHTML = sections.map(s =>
        `<div class="cr-section"><div class="cr-section-title">${esc(s.name)}</div>` +
        s.posts.map(postHtml).join("") + `</div>`
    ).join("");
}

function load() {
    fetch("/classroom/data").then(r => r.json()).then(render).catch(() => {});
}

function crDelete(postId) {
    if (!confirm("Delete this post?")) return;
    fetch(`/classroom/post/${postId}/delete`, { method: "POST", headers: { "X-CSRFToken": csrfToken() } })
        .then(() => load()).catch(() => {});
}

load();
