"""Card Cutter — extract a debate card from a URL or uploaded file.

No LLM/API key required. It pulls the article text + citation metadata, finds the
passage most relevant to what the user asked for, highlights the matching
sentences, and drafts a tag heuristically. (A free LLM key could later replace
`_draft_tag` for smarter tags — everything else stays the same.)
"""
import io
import json
import queue as _q
import re
from html import escape

import trafilatura

from .scraper import submit_fetch
from .citation import citation_fields, format_citation

_HL = 'rgb(253,230,138)'  # same yellow the scraper/library use

_STOP = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with",
    "is", "are", "was", "were", "be", "been", "being", "that", "this", "these",
    "those", "it", "its", "as", "at", "by", "from", "how", "what", "why", "who",
    "which", "will", "would", "can", "could", "should", "do", "does", "about",
    "card", "cards", "evidence", "want", "get", "find", "cut",
}


# ── source extraction ─────────────────────────────────────────────────────────
def _fetch_html(url):
    """Fetch rendered HTML via the real browser (handles JS + bot-blocked sites).

    Falls back to trafilatura's plain fetch if the browser is unavailable.
    """
    try:
        out_q = submit_fetch(url)
        kind, payload = out_q.get(timeout=45)
        if kind == "html" and payload:
            return payload
    except (_q.Empty, Exception):
        pass
    return trafilatura.fetch_url(url)  # fallback


def extract_from_url(url):
    html = _fetch_html(url)
    if not html:
        return None
    data = trafilatura.extract(
        html, url=url, output_format="json", with_metadata=True, favor_recall=True
    )
    if data:
        d = json.loads(data)
        return {
            "text": d.get("text") or "",
            "title": d.get("title") or "",
            "author": d.get("author") or "",
            "date": d.get("date") or "",
            "source": d.get("sitename") or d.get("hostname") or "",
            "url": d.get("source") or url,
        }
    text = trafilatura.extract(html, url=url) or ""
    return {"text": text, "title": "", "author": "", "date": "", "source": "", "url": url}


def extract_from_file(filename, raw_bytes):
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw_bytes))
        return "\n\n".join((pg.extract_text() or "") for pg in reader.pages)
    if name.endswith(".docx"):
        import docx
        doc = docx.Document(io.BytesIO(raw_bytes))
        return "\n\n".join(p.text for p in doc.paragraphs)
    return raw_bytes.decode("utf-8", errors="ignore")


# ── card cutting ──────────────────────────────────────────────────────────────
def _keywords(query):
    return [w for w in re.findall(r"[a-zA-Z][a-zA-Z'-]+", (query or "").lower())
            if w not in _STOP and len(w) > 2]


def _split_paragraphs(text):
    paras = [p.strip() for p in re.split(r"\n{2,}", text or "")]
    return [p for p in paras if len(p) >= 60] or ([text.strip()] if text and text.strip() else [])


def _split_sentences(para):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", para) if s.strip()]


_BAD_AUTHOR = re.compile(
    r"database|authority control|wikipedia|editor|admin|http|www\.|@|cookie|subscribe",
    re.I,
)


def _clean_author(author):
    """Drop obviously-bogus author metadata (nav junk, control databases, etc.)."""
    a = (author or "").strip()
    if not a or len(a) > 60 or len(a.split()) > 5 or _BAD_AUTHOR.search(a):
        return ""
    return a


def _cite_head(author, date):
    year = ""
    m = re.search(r"(19|20)\d{2}", date or "")
    if m:
        year = "'" + m.group(0)[2:]
    last = ""
    if author:
        last = re.sub(r"[^A-Za-z ].*", "", author).strip().split()
        last = last[-1] if last else ""
    # Only a bare year isn't a useful cite head — need an author name.
    if not last:
        return ""
    return " ".join(x for x in [last, year] if x).strip()


def _draft_tag(best_sentences, keywords, cite_head):
    """Heuristic tag: the most keyword-dense sentence, trimmed, with the cite head."""
    if not best_sentences:
        return cite_head or "Untitled card"
    scored = max(best_sentences, key=lambda s: sum(s.lower().count(k) for k in keywords)) \
        if keywords else best_sentences[0]
    words = scored.split()
    short = " ".join(words[:24]) + ("…" if len(words) > 24 else "")
    return f"{cite_head} — {short}" if cite_head else short


def cut_card(meta, query):
    text = meta.get("text") or ""
    if not text.strip():
        return {"ok": False, "error": "No readable text found in that source."}

    kws = _keywords(query)
    paras = _split_paragraphs(text)
    if not paras:
        return {"ok": False, "error": "Couldn't split that source into readable text."}

    def score(p):
        pl = p.lower()
        return sum(pl.count(k) for k in kws)

    best = max(paras, key=score) if kws else paras[0]
    if kws and score(best) == 0:
        best = paras[0]  # nothing matched — fall back to the opening

    sentences = _split_sentences(best)
    parts = []
    for s in sentences:
        if kws and any(k in s.lower() for k in kws):
            parts.append(f'<span style="background-color:{_HL}">{escape(s)}</span>')
        else:
            parts.append(escape(s))
    passage_html = " ".join(parts)

    author = _clean_author(meta.get("author", ""))
    cite_head = _cite_head(author, meta.get("date", ""))
    tag = _draft_tag(sentences, kws, cite_head)

    fields = citation_fields({**meta, "author": author})
    citation = format_citation(**fields)

    return {
        "ok": True,
        "tag": tag,
        "citation": citation,
        "passage_html": passage_html,
        "passage_text": best,
        "matched": bool(kws and score(best) > 0),
    }
