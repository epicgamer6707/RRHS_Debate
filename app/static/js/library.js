// ── Library: search, expand/collapse, formatting, copy, delete ────────────────
let libHL = "Y";

const HL_COLORS = {
    Y: "rgb(253,230,138)",
    G: "rgb(187,247,208)",
    B: "rgb(191,219,254)",
    N: null,
};

function csrfToken() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
}

// ── formatting (font / highlight / variable sizes) applied to every card ───────
function applyLibFormat() {
    const font = document.getElementById("libFont").value;
    const varFont = document.getElementById("libVar").checked;
    let css = `.right-content * { font-family: ${font} !important; }`;
    if (!varFont) css += `\n.right-content span { font-size: 11pt !important; }`;
    document.getElementById("fmtStyle").textContent = css;

    const newColor = HL_COLORS[libHL];
    document.querySelectorAll(".right-content span").forEach(span => {
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

function setLibHL(mode) {
    libHL = mode;
    ["Y", "G", "B", "N"].forEach(m =>
        document.getElementById("hl" + m).classList.toggle("active", m === mode)
    );
    applyLibFormat();
}

// ── expand / collapse ──────────────────────────────────────────────────────────
function toggleCard(head) {
    head.parentElement.classList.toggle("open");
}

// ── full-text search (title + every word of the card) ──────────────────────────
function libSearch() {
    const q = document.getElementById("libSearch").value.trim().toLowerCase();
    let shown = 0;
    document.querySelectorAll(".lib-card").forEach(card => {
        const title = card.querySelector(".lib-card-title").textContent.toLowerCase();
        const raw = (card.querySelector(".lib-raw")?.textContent || "").toLowerCase();
        const match = !q || title.includes(q) || raw.includes(q);
        card.style.display = match ? "" : "none";
        if (match) shown++;
    });
    const c = document.getElementById("libCount");
    if (c) c.textContent = shown + (shown === 1 ? " card" : " cards");
}

// ── copy ───────────────────────────────────────────────────────────────────────
function copyLib(e, id) {
    e.stopPropagation();
    const card = document.querySelector(`.lib-card[data-id="${id}"]`);
    const text = card.querySelector(".lib-raw").textContent;
    const btn = e.currentTarget;
    navigator.clipboard.writeText(text).then(() => {
        const orig = btn.textContent;
        btn.textContent = "Copied!";
        setTimeout(() => { btn.textContent = orig; }, 1500);
    });
}

// ── delete ─────────────────────────────────────────────────────────────────────
function deleteLib(e, id) {
    e.stopPropagation();
    if (!confirm("Delete this card from your library?")) return;
    fetch(`/library/${id}/delete`, {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken() },
    })
    .then(r => r.json())
    .then(data => {
        if (data.ok) {
            const card = document.querySelector(`.lib-card[data-id="${id}"]`);
            if (card) card.remove();
            libSearch();
        }
    });
}

// initial formatting pass
applyLibFormat();
