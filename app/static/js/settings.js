// ── Settings: signature + theme (stored in localStorage) ───────────────────────
function saveSignature() {
    const v = document.getElementById("sigInput").value.trim();
    localStorage.setItem("rrhsSignature", v);
    const n = document.getElementById("sigNote");
    n.hidden = false;
    setTimeout(() => { n.hidden = true; }, 1800);
}

function toggleTheme() {
    const light = document.getElementById("themeToggle").checked;
    const theme = light ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("rrhsTheme", theme);
}

(function init() {
    document.getElementById("sigInput").value = localStorage.getItem("rrhsSignature") || "";
    document.getElementById("themeToggle").checked = localStorage.getItem("rrhsTheme") === "light";
})();
