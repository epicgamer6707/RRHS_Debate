// ── Citation Maker: fetch metadata, build citation live, copy ──────────────────
function csrfToken() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
}

function val(id) { return (document.getElementById(id).value || "").trim(); }

function todayAccessed() {
    const d = new Date();
    return (d.getMonth() + 1) + "/" + d.getDate() + "/" + d.getFullYear();
}

function buildCitation() {
    const last = val("cLast") || "[author]";
    const year = val("cYear") || "[year]";
    const quals = val("cQuals") || "[qualifications]";
    const title = val("cTitle") || "[title]";
    const pub = val("cPub") || "[publication]";
    const url = val("cUrl") || "[url]";
    const sig = val("cSig") || "[signature]";
    const cite = last + " " + year + ", " + quals + ', "' + title + '," ' +
        pub + ", " + url + ", accessed " + todayAccessed() + " | " + sig;
    document.getElementById("citePreview").value = cite;
}

function fetchCitation() {
    const url = val("cUrl");
    const err = document.getElementById("cErr");
    const btn = document.getElementById("cFetchBtn");
    err.hidden = true;
    if (!url) { err.textContent = "Paste a website link first."; err.hidden = false; return; }

    btn.disabled = true;
    btn.textContent = "Fetching...";

    fetch("/citation/fetch", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        body: JSON.stringify({ url }),
    })
    .then(r => r.json())
    .then(data => {
        if (!data.ok) { err.textContent = data.error || "Couldn't fetch that link."; err.hidden = false; return; }
        if (data.last) document.getElementById("cLast").value = data.last;
        if (data.year) document.getElementById("cYear").value = data.year;
        if (data.title) document.getElementById("cTitle").value = data.title;
        if (data.publication) document.getElementById("cPub").value = data.publication;
        if (data.url) document.getElementById("cUrl").value = data.url;
        buildCitation();
    })
    .catch(() => { err.textContent = "Something went wrong. Try again."; err.hidden = false; })
    .finally(() => { btn.disabled = false; btn.textContent = "Fetch details"; });
}

function copyCitation() {
    navigator.clipboard.writeText(document.getElementById("citePreview").value).then(() => {
        const n = document.getElementById("cCopyNote");
        n.hidden = false;
        setTimeout(() => { n.hidden = true; }, 1500);
    });
}

buildCitation();
