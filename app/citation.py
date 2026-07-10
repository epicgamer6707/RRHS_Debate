"""Shared citation formatting.

Format:
  %last% %y%, %quals%, "%title%," %publication%, %url%, accessed %accessed% | [signature]

Missing fields become bracketed placeholders so the citation is a fill-in draft.
"""
import re
from datetime import date


def author_last(author):
    a = (author or "").strip()
    if not a:
        return ""
    a = re.split(r",| and |;|&|/", a)[0].strip()
    parts = re.sub(r"[^A-Za-z .'-]", "", a).split()
    return parts[-1] if parts else ""


def year_of(datestr):
    m = re.search(r"(19|20)\d{2}", datestr or "")
    return m.group(0) if m else ""


def today_accessed():
    return date.today().strftime("%-m/%-d/%Y")


def format_citation(last="", year="", quals="", title="", publication="",
                    url="", accessed="", signature=""):
    return (
        f'{(last or "").strip() or "[author]"} '
        f'{(year or "").strip() or "[year]"}, '
        f'{(quals or "").strip() or "[qualifications]"}, '
        f'"{(title or "").strip() or "[title]"}," '
        f'{(publication or "").strip() or "[publication]"}, '
        f'{(url or "").strip() or "[url]"}, '
        f'accessed {(accessed or "").strip() or today_accessed()} '
        f'| {(signature or "").strip() or "[signature]"}'
    )


def citation_fields(meta):
    """Pull the citation fields we can from extracted metadata."""
    return {
        "last": author_last(meta.get("author", "")),
        "year": year_of(meta.get("date", "")),
        "title": (meta.get("title") or "").strip(),
        "publication": (meta.get("source") or "").strip(),
        "url": (meta.get("url") or "").strip(),
    }
