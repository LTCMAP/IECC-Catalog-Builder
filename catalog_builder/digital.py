"""The digital catalog: a branded, searchable, multi-page static website built from the same
pieces as the print catalog (book.build_book_html parts) plus the FileMaker course data.

One folder per edition:
  <edition>/index.html          home: search, sections, colleges, edition notice
  <edition>/<section-id>.html   one page per catalog section
  <edition>/programs.html       programs by meta major
  <edition>/courses.html        all course descriptions, with filters
  <edition>/addenda.html        addenda (reads addenda.js, which can grow after an edition is frozen)
  <edition>/assets/             css, js, fonts (self-contained; works from a file share, any web host or Drupal files)

Pages load ../catalog-years.js (written at the publish root) to fill the year switcher, so frozen
editions never need rebuilding when a new year is added.
"""
from __future__ import annotations

import html
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from .book import COLLEGE_COLOR, slug, stripes_diag
from .model import CAMPUSES, Course
from .outputs import ASSETS, course_html, group_by_subject, subject_name

esc = html.escape
ID_RE = re.compile(r'\bid="([^"]+)"')
HREF_RE = re.compile(r'href="#([^"]+)"')
CODE_CELL = re.compile(r'<td class="c">([A-Z]{3} \d{3,4}[A-Z]?)</td>')


def _year_slug(year: str) -> str:
    """'2026–2027' -> '2026-27'"""
    m = re.match(r"(\d{4})\D+(\d{2,4})", year)
    return f"{m.group(1)}-{m.group(2)[-2:]}" if m else slug(year)


# ------------------------------------------------------------------ page shell
def _nav(pages: list[dict], current: str) -> str:
    items = []
    for p in pages:
        cur = p["file"] == current
        subs = ""
        if cur and p.get("subs"):
            subs = "<ul>" + "".join(f'<li><a href="#{a}">{esc(t)}</a></li>' for t, a in p["subs"][:40]) + "</ul>"
        num = f'<span class="n">{p["num"]}</span>' if p.get("num") else '<span class="n"></span>'
        items.append(f'<li{" class=cur" if cur else ""}><a href="{p["file"]}"{" aria-current=page" if cur else ""}>{num}{esc(p["title"])}</a>{subs}</li>')
    return f'<nav class="side" id="side" aria-label="Catalog sections"><ol>{"".join(items)}</ol></nav>'


def _shell(ed: dict, title: str, body: str, nav: str, file: str, wide: bool = False) -> str:
    pdf = '<a class="btn ghost" href="catalog.pdf" download>PDF</a>' if ed["has_pdf"] else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · {esc(ed["year"])} Academic Catalog · {esc(ed["district"])}</title>
<meta name="description" content="{esc(ed["year"])} Academic Catalog, {esc(ed["district"])}: programs, courses, policies and academic information.">
{'' if ed["kind"] == "current" else f'<link rel="canonical" href="../current/{file}">' if ed.get("canonical") else ''}
<link rel="stylesheet" href="assets/site.css">
<script>window.IECC_EDITION={json.dumps({"kind": ed["kind"], "year": ed["year"], "slug": ed["slug"], "built": ed["built"], "record": ed.get("record", "")})};</script>
<script src="../catalog-years.js" defer onerror="this.remove()"></script>
<script src="addenda.js" defer></script>
<script src="search-index.js" defer></script>
<script src="assets/site.js" defer></script>
</head><body>
<a class="skip" href="#main">Skip to content</a>
<header class="top"><div class="bar">
  <button class="menu" aria-controls="side" aria-expanded="false" aria-label="Sections menu"><span></span><span></span><span></span></button>
  <a class="brand" href="index.html"><span class="d">{esc(ed["district"])}</span><span class="t">Academic Catalog</span></a>
  <label class="year"><span class="sr">Catalog year</span><select id="year-switch" aria-label="Catalog year"><option>{esc(ed["year"])}</option></select></label>
  <div class="search" role="search"><label class="sr" for="q">Search the catalog</label>
    <input id="q" type="search" placeholder="Search programs, courses, policies…" autocomplete="off" aria-controls="results" aria-expanded="false">
    <div id="results" class="results" role="listbox" hidden></div></div>
  {pdf}
</div><div class="stripe" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div></header>
<div id="edition-banner" class="banner" role="note"></div>
<div class="layout{' wide' if wide else ''}">{nav}<main id="main" tabindex="-1">{body}</main></div>
<footer class="foot"><div>{esc(ed["district"])} · {esc(ed["year"])} Academic Catalog · Built {esc(ed["built"])}</div>
<div><a href="addenda.html">Addenda</a>{' · <a href="catalog.pdf">Printable PDF</a>' if ed["has_pdf"] else ''} · <a href="{esc(ed["url_full"])}">iecc.edu/catalog</a></div></footer>
</body></html>"""


# ------------------------------------------------------------------ build
def build_site(courses: list[Course], prefixes: dict, parts: dict, out_dir: Path, *, kind: str = "current",
               built: str | None = None, pdf: Path | None = None, record: str = "") -> dict:
    """Write one edition. kind = 'current' (live, updated every build) or 'frozen' (edition of record)."""
    cat = parts["cat"]
    out_dir.mkdir(parents=True, exist_ok=True)
    ed = {"kind": kind, "year": cat["year"], "slug": _year_slug(cat["year"]), "district": cat["district"],
          "built": built or (lambda d: f"{d:%B} {d.day}, {d.year}")(datetime.now()), "has_pdf": bool(pdf and pdf.exists()),
          "url_full": "https://" + cat["url"].removeprefix("https://").removeprefix("http://"),
          "canonical": kind == "frozen", "record": record}

    # page list (order = print order)
    pages = [{"file": "index.html", "title": "Catalog Home", "num": ""}]
    for f in parts["front"]:
        pages.append({"file": f"{f['id']}.html", "title": f["title"], "num": "", "html": f'<div class="prose">{f["html"]}</div>', "subs": f["subs"], "id": f["id"]})
    for s in parts["sections"]:
        if s["type"] == "courses":
            pages.append({"file": "courses.html", "title": s["title"], "num": s["num"], "kind": "courses", "subs": []})
        else:
            pages.append({"file": f"{s['id']}.html", "title": s["title"], "num": s["num"], "html": s["html"], "subs": s["subs"], "id": s["id"], "auto": s.get("auto", "")})
    if parts.get("program_index"):
        pages.append({"file": "programs.html", "title": "Programs by Meta Major", "num": "", "html": parts["program_index"],
                      "subs": [(html.unescape(t), a) for a, t in re.findall(r'<h2 id="(mm-[^"]+)">([^<]+?) <span', parts["program_index"])], "id": "program-index"})
    pages.append({"file": "addenda.html", "title": "Addenda", "num": ""})

    # course page body
    groups = group_by_subject(courses, prefixes)
    subj_opts = "".join(f'<option value="{p}">{p} · {esc(subject_name(p, prefixes))}</option>' for p in groups)
    camp_opts = "".join(f'<label class="chk"><input type="checkbox" value="{c}"><i class="on {c}">{l}</i>{esc(n)}</label>' for c, l, n in CAMPUSES)
    subj_blocks = "".join(
        f'<section class="subject" id="s-{p}" data-p="{p}"><h2><span class="chip">{p}</span>{esc(subject_name(p, prefixes))}<span class="count">{len(cs)}</span></h2>'
        + "".join(course_html(c) for c in cs) + "</section>" for p, cs in groups.items())
    course_page = (f'<div class="page-head"><p class="kicker">Section {next((p["num"] for p in pages if p.get("kind") == "courses"), "")}</p><h1>Course Descriptions</h1>'
                   f'<p class="lede">{len(courses):,} courses in {len(groups)} subjects, straight from the college\'s course records. Filter by subject, campus or keyword.</p></div>'
                   f'<form class="filters" onsubmit="return false"><label>Subject<select id="f-subj"><option value="">All subjects</option>{subj_opts}</select></label>'
                   f'<label>Keyword<input id="f-text" type="search" placeholder="e.g. welding, ENG 1111, IAI"></label>'
                   f'<fieldset><legend>Offered at</legend>{camp_opts}</fieldset><p id="f-count" class="count" aria-live="polite"></p></form>'
                   f'<div class="courses" id="course-list">{subj_blocks}</div>')

    # where every anchor lives, so cross-page links work
    anchor_page: dict[str, str] = {}
    for p in pages:
        if p.get("html"):
            for a in ID_RE.findall(p["html"]):
                anchor_page.setdefault(a, p["file"])
            if p.get("id"):
                anchor_page.setdefault(p["id"], p["file"])
    for p_ in groups:
        anchor_page[f"s-{p_}"] = "courses.html"
    for c in courses:
        anchor_page[f"c-{c.prefix}{c.number}"] = "courses.html"
    known = {c.code for c in courses}

    def fix_links(h: str, file: str) -> str:
        h = HREF_RE.sub(lambda m: f'href="{anchor_page[m.group(1)]}#{m.group(1)}"' if anchor_page.get(m.group(1), file) != file else m.group(0), h)
        h = h.replace('<a class="pg" href=', '<a class="pg" aria-label="Program page" href=')
        # course codes in program tables link to their description
        return CODE_CELL.sub(lambda m: f'<td class="c"><a href="courses.html#c-{m.group(1).replace(" ", "")}">{m.group(1)}</a></td>' if m.group(1) in known else m.group(0), h)

    search = []
    for p in pages:
        file = p["file"]
        nav = _nav(pages, file)
        if file == "index.html":
            body = _home(cat, pages, parts, len(courses), len(groups), ed)
            html_ = _shell(ed, "Home", body, "", file, wide=True)
        elif file == "courses.html":
            html_ = _shell(ed, "Course Descriptions", course_page, nav, file)
        elif file == "addenda.html":
            body = ('<div class="page-head"><h1>Addenda</h1><p class="lede">Approved changes to this catalog after it was published, newest first. '
                    'Each addendum lists its effective date.</p></div><div id="addenda-list" class="addenda"><p>Loading…</p></div>'
                    '<noscript><p>Turn on JavaScript to list addenda, or download the PDF addenda from iecc.edu/catalog.</p></noscript>')
            html_ = _shell(ed, "Addenda", body, nav, file)
        else:
            kicker = f'<p class="kicker">Section {p["num"]}</p>' if p.get("num") else ""
            auto = f'<p class="auto">{esc(p["auto"])}</p>' if p.get("auto") else ""
            toc = ""
            if len(p.get("subs") or []) > 3:
                toc = '<details class="on-page" open><summary>On this page</summary><ul>' + "".join(f'<li><a href="#{a}">{esc(t)}</a></li>' for t, a in p["subs"][:60]) + "</ul></details>"
            pager = _pager(pages, file)
            body = f'<div class="page-head">{kicker}<h1>{esc(p["title"])}</h1>{auto}</div>{toc}<div class="content">{fix_links(p["html"], file)}</div>{pager}'
            html_ = _shell(ed, p["title"], body, nav, file)
        (out_dir / file).write_text(html_, encoding="utf-8")
        # search entries
        if file not in ("index.html", "addenda.html", "courses.html"):
            search.append({"t": p["title"], "k": "Section", "u": file})
            for t, a in p.get("subs") or []:
                search.append({"t": t, "k": p["title"], "u": f"{file}#{a}"})
    for pg in re.findall(r'<section class="program" id="([^"]+)">.*?<h2>(.*?)</h2>', "".join(p.get("html", "") for p in pages), re.S):
        search.append({"t": html.unescape(pg[1]), "k": "Program", "u": f"{anchor_page.get(pg[0], 'programs.html')}#{pg[0]}"})
    seen = {e["t"] for e in search if e["k"] == "Program"}
    for mm_id, mm_title, rows in re.findall(r'<div class="mm"><h2 id="([^"]+)">(.*?) <span.*?<tbody>(.*?)</tbody>', parts.get("program_index", ""), re.S):
        for t, ty, code, pg in re.findall(r'<tr><td class="t">(.*?)</td><td class="d">.*?</td><td class="ty">(.*?)</td><td class="cd">(.*?)</td>.*?<td class="p">(.*?)</td></tr>', rows, re.S):
            title = html.unescape(t)
            if title in seen:
                continue
            m = re.search(r'href="#([^"]+)"', pg)
            url = f"{anchor_page.get(m.group(1), 'programs.html')}#{m.group(1)}" if m else f"programs.html#{mm_id}"
            search.append({"t": title, "k": f"Program · {html.unescape(ty)} · {code}", "u": url, "x": html.unescape(mm_title)})
    for p_, cs in groups.items():
        search.append({"t": subject_name(p_, prefixes), "k": f"Subject · {p_}", "u": f"courses.html#s-{p_}"})
        for c in cs:
            search.append({"t": f"{c.code} {c.title}", "k": "Course", "u": f"courses.html#c-{c.prefix}{c.number}", "x": c.description[:140]})

    (out_dir / "search-index.js").write_text("window.IECC_SEARCH=" + json.dumps(search, ensure_ascii=False, separators=(",", ":")) + ";", encoding="utf-8")
    if not (out_dir / "addenda.js").exists():  # never overwrite approved addenda
        (out_dir / "addenda.js").write_text("window.IECC_ADDENDA=[];\n", encoding="utf-8")
    a = out_dir / "assets"
    (a / "fonts").mkdir(parents=True, exist_ok=True)
    for f in (ASSETS / "fonts").glob("*.woff2"):
        shutil.copy2(f, a / "fonts" / f.name)
    shutil.copy2(ASSETS / "site.css", a / "site.css")
    shutil.copy2(ASSETS / "site.js", a / "site.js")
    if ed["has_pdf"]:
        shutil.copy2(pdf, out_dir / "catalog.pdf")
    return {"pages": len(pages), "search": len(search), "slug": ed["slug"]}


def _pager(pages, file):
    files = [p for p in pages if p["file"] not in ("index.html", "addenda.html")]
    i = next((k for k, p in enumerate(files) if p["file"] == file), None)
    if i is None:
        return ""
    prev = files[i - 1] if i > 0 else None
    nxt = files[i + 1] if i + 1 < len(files) else None
    a = f'<a class="prev" href="{prev["file"]}"><span>Previous</span>{esc(prev["title"])}</a>' if prev else "<span></span>"
    b = f'<a class="next" href="{nxt["file"]}"><span>Next</span>{esc(nxt["title"])}</a>' if nxt else "<span></span>"
    return f'<nav class="pager" aria-label="Previous and next section">{a}{b}</nav>'


def _home(cat, pages, parts, n_courses, n_subjects, ed):
    cards = []
    for p in pages:
        if p["file"] in ("index.html", "addenda.html"):
            continue
        n = f'<span class="n">{p["num"]}</span>' if p.get("num") else ""
        cards.append(f'<li><a href="{p["file"]}">{n}<span class="t">{esc(p["title"])}</span></a></li>')
    colleges = "".join(
        f'<div class="college" style="--c:{COLLEGE_COLOR[c["code"]]}"><h3>{esc(c["name"])}</h3><p>{esc(c["address"])}<br>{esc(c["city"])}<br>'
        f'<a href="tel:{c["phone"]}">{esc(c["phone"])}</a></p></div>' for c in cat["colleges"])
    quick = [("programs.html", "Find a program", f'{parts.get("program_count", "")} degrees, certificates and transfer pathways by meta major'),
             ("courses.html", "Course descriptions", f"{n_courses:,} courses in {n_subjects} subjects"),
             ("academic-calendar.html", "Academic calendar", "Term dates, breaks and deadlines")]
    quick_html = "".join(f'<a class="q" href="{u}"><b>{t}</b><span>{d}</span></a>' for u, t, d in quick if any(p["file"] == u for p in pages))
    return (f'<section class="hero"><div class="art" aria-hidden="true">{stripes_diag(900, 520, 34, 18, 0.5)}</div>'
            f'<div class="in"><p class="kicker">{esc(cat["district"])}</p><h1><span>{esc(cat["year"])}</span>Academic Catalog</h1>'
            f'<p class="lede">Programs, courses, policies and everything you need to plan your path at Frontier, Lincoln Trail, Olney Central and Wabash Valley.</p>'
            f'<div class="hero-search"><label class="sr" for="q2">Search the catalog</label><input id="q2" type="search" placeholder="Try “nursing”, “ENG 1111” or “refund”" autocomplete="off"></div>'
            f'<div class="actions">{"<a class=btn href=catalog.pdf download>Download the PDF</a>" if ed["has_pdf"] else ""}<a class="btn ghost light" href="addenda.html">Addenda</a></div></div></section>'
            f'<section class="quick">{quick_html}</section>'
            f'<section class="sections"><h2>In this catalog</h2><ol class="cards">{"".join(cards)}</ol></section>'
            f'<section class="colleges"><h2>Our colleges</h2><div class="grid">{colleges}</div></section>')


def write_years_js(site_root: Path) -> list[dict]:
    """Scan the publish root for edition folders and write catalog-years.js for every page's year switcher."""
    years = []
    for d in sorted(site_root.iterdir(), reverse=True):
        if d.is_dir() and re.fullmatch(r"\d{4}-\d{2}", d.name) and (d / "index.html").exists():
            years.append({"slug": d.name, "label": f"{d.name[:4]}–20{d.name[5:]}"})
    if (site_root / "current" / "index.html").exists():
        years.insert(0, {"slug": "current", "label": "Current catalog"})
    (site_root / "catalog-years.js").write_text("window.IECC_YEARS=" + json.dumps(years, ensure_ascii=False) + ";\n", encoding="utf-8")
    return years
