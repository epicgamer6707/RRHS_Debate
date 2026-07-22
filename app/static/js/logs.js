// Shared to-do list on the Logs page (public — anyone can add / check off).
function _csrf() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
}
function _post(url, body) {
    return fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": _csrf() },
        body: JSON.stringify(body || {}),
    }).then(r => r.json());
}
function esc(s) {
    return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function _refreshEmpty() {
    const list = document.getElementById("todoList");
    const empty = document.getElementById("todoEmpty");
    empty.hidden = list.children.length > 0;
}

function todoAdd() {
    const input = document.getElementById("todoInput");
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    _post("/logs/todo/add", { text }).then(d => {
        if (!d.ok) return;
        const li = document.createElement("li");
        li.className = "todo-item";
        li.dataset.id = d.id;
        li.innerHTML =
            `<button class="todo-check" onclick="todoDone(${d.id})" title="Check off"><span class="todo-box"></span></button>` +
            `<span class="todo-text">${esc(d.text)}</span>`;
        document.getElementById("todoList").appendChild(li);
        _refreshEmpty();
    });
}

function todoDone(id) {
    const li = document.querySelector(`.todo-item[data-id="${id}"]`);
    if (li) li.classList.add("checking");
    _post(`/logs/todo/${id}/done`).then(d => {
        if (d.ok && li) {
            li.addEventListener("transitionend", () => { li.remove(); _refreshEmpty(); }, { once: true });
            // fallback if no transition fires
            setTimeout(() => { if (li.isConnected) { li.remove(); _refreshEmpty(); } }, 300);
        } else if (li) {
            li.classList.remove("checking");
        }
    });
}
